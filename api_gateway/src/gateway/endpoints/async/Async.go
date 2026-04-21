package async

import (
	"encoding/json"
	"errors"
	"fmt"
	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
	"net/http"
	"transcriber-api-gateway/src/database"
	"transcriber-api-gateway/src/gateway"
	"transcriber-api-gateway/src/gateway/endpoints"
)

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

		jobID := c.Param("job_id")

		err := validateJobId(jobID)

		if err != nil {
			endpoints.SendErrorMessage(c, http.StatusBadRequest, err.Error())
			return
		}

		jobRow, err := jobRepo.GetJobById(c, jobID)

		if errors.Is(err, database.ErrRowDoesNotExists) {
			endpoints.SendErrorMessage(c, http.StatusNotFound, err.Error())

			return
		}

		if err != nil {
			endpoints.SendErrorMessage(c, http.StatusInternalServerError, err.Error())
			return
		}

		jobStatus := jobRow.Status

		if jobRow.Mode != database.JobModAsync {
			endpoints.SendErrorMessage(c, http.StatusNotFound, "Job is not found with provided ID")
			return
		}

		switch jobStatus {
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
			needDownload := c.Query("download") == "true"

			exists, err := storage.FolderExists(c, jobID)

			if err != nil {
				endpoints.SendErrorMessage(c, http.StatusInternalServerError, err.Error())
				return
			}

			if !exists {
				endpoints.SendErrorMessage(c, http.StatusInternalServerError, "Result for job is not found with provided job ID")
				return
			}

			resultDir := jobID + "/result.json"
			exists, err = storage.Exists(c, resultDir)

			if err != nil {
				endpoints.SendErrorMessage(c, http.StatusInternalServerError, err.Error())
				return
			}

			if !exists {
				endpoints.SendErrorMessage(c, http.StatusInternalServerError, "Result for job is not found with provided job ID")
				return
			}

			fileBytes, err := storage.GetBytes(c, resultDir)

			if err != nil {
				c.JSON(http.StatusInternalServerError, err.Error())
				return
			}

			if needDownload {
				c.Header("Content-Disposition", "attachment")
				c.Data(http.StatusOK, "application/octet-stream", fileBytes)

				return
			}

			// Иначе отправляем json
			var data gin.H
			err = json.Unmarshal(fileBytes, &data)

			if err != nil {
				endpoints.SendErrorMessage(c, http.StatusInternalServerError, err.Error())
				return
			}

			c.JSON(http.StatusOK, data)
			return
		}
	}
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

		jobId, err := apiCtx.DatabaseContext.JobRepository.CreateAsyncJob(c, userId)

		if err != nil {
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
		}

		apiCtx.Logger.Println(fmt.Sprintf("Job created with ID: %s, %s", jobId, dir))

		c.JSON(http.StatusOK, gin.H{
			"job_id": jobId,
			"status": database.JobStatusPending,
			"error":  false,
		})

	}
}
