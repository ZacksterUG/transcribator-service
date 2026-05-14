package async

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"net/http"
	"net/url"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
	"github.com/redis/go-redis/v9"

	"transcriber-api-gateway/src/database"
	"transcriber-api-gateway/src/gateway"
	"transcriber-api-gateway/src/gateway/endpoints"
	"transcriber-api-gateway/src/minio"
)

const asyncJobResultCacheTTL = 24 * time.Hour

func RegisterAsyncEndpoints(ctx *gateway.Context) {
	authHandler := ctx.AuthHandler

	group := ctx.Group.Group("/async")
	{
		group.GET(
			"/job/:job_id",
			authHandler.RequireAuth(),
			authHandler.RequireRole("transcriber"),
			GetJob(ctx),
		)
		group.POST(
			"/job",
			authHandler.RequireAuth(),
			authHandler.RequireRole("transcriber"),
			PostJob(ctx),
		)
	}
}

func validateJobId(job string) error {
	_, err := uuid.Parse(job)

	return err
}

func GetJob(apiCtx *gateway.Context) gin.HandlerFunc {
	return func(c *gin.Context) {
		jobRepo := apiCtx.DatabaseContext.JobRepository
		storage := apiCtx.Storage
		logger := apiCtx.Logger
		redis := apiCtx.Redis

		jobID := c.Param("job_id")
		cacheRedisKey := fmt.Sprintf("transcriber:async:%s:result_cache", jobID)
		needDownload := c.Query("download") == "true"
		err := validateJobId(jobID)

		if err != nil {
			endpoints.SendErrorMessage(c, http.StatusBadRequest, err.Error())
			return
		}

		fileBytes, err := getCachedJobResult(c.Request.Context(), cacheRedisKey, redis)
		if err == nil {
			sendDataWithDownload(c, fileBytes, needDownload)
			logger.Println(fmt.Sprintf("Result from job %s was retrieved from cache", jobID))
			return
		}

		jobRow, ok := getJobRowData(c, jobRepo, jobID)

		if !ok {
			return
		}

		switch jobRow.Status {
		case database.JobStatusPending:
			c.JSON(http.StatusOK, gin.H{
				"job_id": jobID,
				"status": database.JobStatusPending,
				"error":  false,
			})
			return
		case database.JobStatusInProgress:
			c.JSON(http.StatusOK, gin.H{
				"job_id": jobID,
				"status": database.JobStatusInProgress,
				"error":  false,
			})
			return
		case database.JobStatusFailed:
			c.JSON(http.StatusOK, gin.H{
				"job_id":  jobID,
				"status":  database.JobStatusFailed,
				"error":   true,
				"message": jobRow.ErrorMessage,
			})
			return
		case database.JobStatusFinished:
			fileBytes, err = getJobResultFromStorage(c.Request.Context(), storage, jobID)

			if err != nil {
				endpoints.SendErrorMessage(c, http.StatusInternalServerError, err.Error())

				return
			}

			go setCachedJobResult(apiCtx, cacheRedisKey, asyncJobResultCacheTTL, fileBytes)
		}

		sendDataWithDownload(c, fileBytes, needDownload)
	}
}

func getCachedJobResult(ctx context.Context, jobResultCacheKey string, redis *redis.Client) ([]byte, error) {
	rgCtx, rgCtxCancel := context.WithTimeout(ctx, 5*time.Second)
	defer rgCtxCancel()
	jobCachedValue := redis.Get(rgCtx, jobResultCacheKey)

	return jobCachedValue.Bytes()
}

func setCachedJobResult(apiCtx *gateway.Context, jobResultCacheKey string, ttlSeconds time.Duration, value []byte) {
	rgCtx, rgCtxCancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer rgCtxCancel()

	jobCachedValue := apiCtx.Redis.Set(rgCtx, jobResultCacheKey, value, ttlSeconds)

	if err := jobCachedValue.Err(); err != nil {
		apiCtx.Logger.Printf("error caching key '%s': %v", jobResultCacheKey, err)
	}
}

func getJobResultFromStorage(c context.Context, storage *minio.MinIOClient, jobID string) ([]byte, error) {
	exists, err := storage.FolderExists(c, jobID)
	if err != nil {
		return nil, err
	}
	if !exists {
		return nil, errors.New("result for job is not found with provided job ID")
	}

	resultDir := jobID + "/result.json"
	exists, err = storage.Exists(c, resultDir)
	if err != nil {
		return nil, err
	}

	if !exists {
		return nil, errors.New("result for job is not found with provided job ID")
	}

	fileBytes, err := storage.GetBytes(c, resultDir)

	if err != nil {
		return nil, err
	}

	return fileBytes, nil
}

func getJobRowData(c *gin.Context, jobRepo *database.JobRepository, jobID string) (*database.JobModel, bool) {
	jobRow, err := jobRepo.GetJobById(c.Request.Context(), jobID)

	if errors.Is(err, database.ErrRowDoesNotExists) {
		endpoints.SendErrorMessage(c, http.StatusNotFound, err.Error())

		return nil, false
	}

	if err != nil {
		endpoints.SendErrorMessage(c, http.StatusInternalServerError, err.Error())

		return nil, false
	}

	if jobRow.Mode != database.JobModAsync {
		endpoints.SendErrorMessage(c, http.StatusNotFound, "Job is not found with provided ID")

		return nil, false
	}

	return jobRow, true
}

func validateWebhookParams(c *gin.Context, logger *log.Logger) error {
	webhookURL := c.PostForm("webhook_url")
	method := c.PostForm("webhook_method")
	headers := c.PostForm("webhook_headers")

	hasWebhookData := webhookURL != "" || method != "" || headers != ""

	if hasWebhookData && webhookURL == "" {
		err := errors.New("webhook_url is required when webhook_method or webhook_headers are provided")
		logger.Printf("Validation error: %v", err)
		return err
	}

	if webhookURL == "" {
		return nil
	}

	if _, err := url.ParseRequestURI(webhookURL); err != nil {
		err := errors.New("invalid webhook_url: must be a valid URL")
		logger.Printf("Validation error: %v", err)
		return err
	}

	effectiveMethod := c.DefaultPostForm("webhook_method", "POST")
	if effectiveMethod != "POST" && effectiveMethod != "PUT" {
		err := errors.New("invalid webhook_method: must be POST or PUT")
		logger.Printf("Validation error: %v", err)
		return err
	}

	if headers != "" {
		var dummy map[string]interface{}
		if err := json.Unmarshal([]byte(headers), &dummy); err != nil {
			err := errors.New("invalid webhook_headers: must be valid JSON")
			logger.Printf("Validation error: %v", err)
			return err
		}
	}

	return nil
}

func saveWebhookConfig(c *gin.Context, apiCtx *gateway.Context, jobId string) error {
	webhookURL := c.PostForm("webhook_url")
	if webhookURL == "" {
		return nil
	}

	method := c.DefaultPostForm("webhook_method", "POST")
	headers := c.DefaultPostForm("webhook_headers", "{}")

	_, err := apiCtx.DatabaseContext.WebhookRepository.CreateWebhookConfig(
		c.Request.Context(),
		jobId,
		webhookURL,
		method,
		headers,
	)

	if err != nil {
		apiCtx.Logger.Printf("Error creating webhook config for job %s: %v", jobId, err)
		return err
	}

	return nil
}

func sendDataWithDownload(c *gin.Context, dataBytes []byte, needDownload bool) {
	if needDownload {
		c.Header("Content-Disposition", "attachment")
		c.Data(http.StatusOK, "application/octet-stream", dataBytes)

		return
	}

	var data gin.H
	err := json.Unmarshal(dataBytes, &data)

	if err != nil {
		endpoints.SendErrorMessage(c, http.StatusInternalServerError, err.Error())
		return
	}

	c.JSON(http.StatusOK, data)
}

func PostJob(apiCtx *gateway.Context) gin.HandlerFunc {
	return func(c *gin.Context) {
		file, header, err := c.Request.FormFile("file")

		if err != nil {
			endpoints.SendErrorMessage(c, http.StatusNotFound, "file not provided")
			return
		}

		defer file.Close()

		var FileMaxSize int64 = 100 * 1024 * 1024 // 100 MB

		if header.Size > FileMaxSize {
			endpoints.SendErrorMessage(c, http.StatusBadRequest, "file too large")
			return
		}

		if header.Size <= 0 {
			endpoints.SendErrorMessage(c, http.StatusBadRequest, "file size must be provided")
			return
		}

		audioTypesAllowed := []string{
			"audio/wav", "audio/x-wav", "audio/mpeg", "audio/ogg", "audio/flac", "audio/mp4",
		}

		mimeType, err := endpoints.DetectAudioType(file, audioTypesAllowed)

		if err != nil {
			endpoints.SendErrorMessage(c, http.StatusBadRequest, "invalid audio file")
			return
		}

		userId, err := apiCtx.AuthHandler.Authorizer.GetUserID(c)

		if err != nil {
			endpoints.SendErrorMessage(c, http.StatusInternalServerError, err.Error())
			return
		}

		if err := validateWebhookParams(c, apiCtx.Logger); err != nil {
			endpoints.SendErrorMessage(c, http.StatusBadRequest, err.Error())
			return
		}

		jobId, err := apiCtx.DatabaseContext.JobRepository.CreateAsyncJob(c, userId)

		if err != nil {
			endpoints.SendErrorMessage(c, http.StatusInternalServerError, err.Error())
			return
		}

		if err := saveWebhookConfig(c, apiCtx, jobId); err != nil {
			endpoints.SendErrorMessage(c, http.StatusInternalServerError, err.Error())
			return
		}

		fileName := header.Filename
		dir := jobId + "/" + fileName

		err = apiCtx.Storage.Put(c, dir, file, header.Size, mimeType)

		if err != nil {
			endpoints.SendErrorMessage(c, http.StatusInternalServerError, err.Error())
			return
		}

		// Создание задачи на асинхронную обработку
		err = apiCtx.NatsContext.CreateAsyncJobFile(c, jobId, apiCtx.Storage.GetDefaultBucket()+"/"+dir)

		if err != nil {
			endpoints.SendErrorMessage(c, http.StatusInternalServerError, err.Error())
			return
		}

		apiCtx.Logger.Println(fmt.Sprintf("Job created with ID: %s, %s", jobId, dir))

		c.JSON(http.StatusOK, gin.H{
			"job_id": jobId,
			"status": database.JobStatusPending,
			"error":  false,
		})
	}
}
