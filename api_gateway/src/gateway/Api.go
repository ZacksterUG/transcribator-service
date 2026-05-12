package gateway

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"time"

	natslib "github.com/nats-io/nats.go"
	"github.com/nats-io/nats.go/jetstream"

	"github.com/bsm/redislock"
	"github.com/gin-gonic/gin"
	"github.com/redis/go-redis/v9"

	"transcriber-api-gateway/src/database"
	"transcriber-api-gateway/src/gateway/middleware/accessLogging"
	"transcriber-api-gateway/src/gateway/middleware/authorization"
	"transcriber-api-gateway/src/minio"
	"transcriber-api-gateway/src/nats"
	"transcriber-api-gateway/src/utils"
	"transcriber-api-gateway/src/webhook"
)

type GatewayInstance struct {
	ctx                  context.Context
	ginInstance          *gin.Engine
	cfg                  GatewayConfig
	authorizer           authorization.Authorizer
	logger               *log.Logger
	storage              *minio.MinIOClient
	redis                *redis.Client
	databaseContext      *database.DatabaseContext
	natsContext          *nats.NatsContext
	webhookSender        *webhook.WebhookSender
	accessLogRepository  *database.AccessLogRepository
}

type GatewayConfig struct {
	Port string
}

type Context struct {
	AuthHandler     authorization.AuthHandler
	Logger          *log.Logger
	Group           *gin.RouterGroup
	Storage         *minio.MinIOClient
	Redis           *redis.Client
	DatabaseContext *database.DatabaseContext
	NatsContext     *nats.NatsContext
	WebhookSender   *webhook.WebhookSender
}

func Gateway(
	ctx context.Context,
	logger *log.Logger,
	Auth authorization.Authorizer,
	Storage *minio.MinIOClient,
	redisClient *redis.Client,
	config GatewayConfig,
	databaseContext *database.DatabaseContext,
	natsContext *nats.NatsContext,
	webhookSender *webhook.WebhookSender,
	accessLogRepository *database.AccessLogRepository,
) *GatewayInstance {
	g := gin.Default()

	agi := GatewayInstance{
		ctx:                  ctx,
		ginInstance:          g,
		cfg:                  config,
		authorizer:           Auth,
		logger:               logger,
		storage:              Storage,
		redis:                redisClient,
		databaseContext:      databaseContext,
		natsContext:          natsContext,
		webhookSender:        webhookSender,
		accessLogRepository: accessLogRepository,
	}

	return &agi
}

func (agi *GatewayInstance) Start() error {
	return agi.ginInstance.Run(":" + agi.cfg.Port)
}

type RegisterHandler func(*Context)

func (agi *GatewayInstance) Setup(handlers []RegisterHandler) {
	authHandler := authorization.NewAuthHandler(agi.authorizer)

	// Создаем основную группу API
	apiGroup := agi.ginInstance.Group("/api")

	if agi.accessLogRepository != nil {
		accessLogMiddleware := accessLogging.NewAccessLoggingMiddleware(agi.accessLogRepository, agi.logger)
		apiGroup.Use(accessLogMiddleware.Handler("api.access"))
	}

	context := &Context{
		Group:           apiGroup,
		AuthHandler:     *authHandler,
		Logger:          agi.logger,
		Storage:         agi.storage,
		Redis:           agi.redis,
		DatabaseContext: agi.databaseContext,
		NatsContext:     agi.natsContext,
		WebhookSender:   agi.webhookSender,
	}

	for _, handler := range handlers {
		handler(context)
	}

	err := agi.natsContext.Subscribe(
		agi.ctx,
		agi.HandleAsyncResponses(),
		agi.HandleSyncStatusFinish(),
	)

	if err != nil {
		log.Fatal("Error subscribing to NATS topic:", err)
	}
}

func (agi *GatewayInstance) HandleAsyncResponses() func(jetstream.Msg) {
	return func(msg jetstream.Msg) {
		err := msg.Ack()
		logger := agi.logger

		if err != nil {
			logger.Println("Error acknowledging message:", err)
			return
		}

		data := msg.Data()

		jsonData := map[string]any{}
		err = json.Unmarshal(data, &jsonData)

		if err != nil {
			logger.Printf("Error unmarshalling json: %v", err)
			return
		}

		jobId := jsonData["job_id"].(string)
		status := jsonData["status"].(string)

		logger.Printf("Received async response: %v, status: %v", jobId, status)

		completedAtStr := jsonData["completed_at"].(string)
		completedAt, err := time.Parse(time.RFC3339, completedAtStr)
		errorMessage := ""

		if status == database.JobStatusFailed {
			errorMessage = jsonData["error"].(string)
		}

		err = agi.databaseContext.JobRepository.UpdateJobStatus(
			agi.ctx,
			jobId,
			status,
			completedAt,
			errorMessage,
		)

		if err != nil {
			logger.Printf("Error updating job status: %v", err)
			return
		}

		if status == database.JobStatusFinished || status == database.JobStatusFailed {
			go func() {
				agi.sendWebhookForJob(jobId, status, completedAtStr, errorMessage)
			}()
		}
	}
}

func (agi *GatewayInstance) sendWebhookForJob(jobID, status, completedAt, errorMessage string) {
	webhookConfig, err := agi.databaseContext.WebhookRepository.GetWebhookConfigByJobID(agi.ctx, jobID)
	if err != nil {
		agi.logger.Printf("No webhook config found for job %s", jobID)
		return
	}

	var headers map[string]string
	if webhookConfig.Headers != "" {
		if err := json.Unmarshal([]byte(webhookConfig.Headers), &headers); err != nil {
			agi.logger.Printf("Error parsing webhook headers for job %s: %v", jobID, err)
			headers = nil
		}
	}

	var resultData interface{}

	if status == database.JobStatusFinished {
		resultPath := jobID + "/result.json"

		var fileBytes []byte
		exists := false
		var err error

		for i := 0; i < 5; i++ {
			exists, err = agi.storage.Exists(agi.ctx, resultPath)
			if err == nil && exists {
				break
			}
			agi.logger.Printf("Waiting for result file... attempt %d/5", i+1)
			time.Sleep(2 * time.Second)
		}

		if exists && err == nil {
			fileBytes, err = agi.storage.GetBytes(agi.ctx, resultPath)
			if err == nil {
				var jsonData map[string]interface{}
				if json.Unmarshal(fileBytes, &jsonData) == nil {
					resultData = jsonData
				}
			} else {
				agi.logger.Printf("Error downloading file for webhook result for job %s: %v", jobID, err)
			}
		} else {
			status = database.JobStatusFailed
			errorMessage = "Result file not found in storage after 5 attempts"
			agi.logger.Printf("Result file not found for job %s after 5 attempts", jobID)
		}
	}

	payload := webhook.WebhookPayload{
		JobID:       jobID,
		Status:      status,
		CompletedAt: completedAt,
		Result:      resultData,
		Error:       errorMessage,
	}

	method := "POST"
	if webhookConfig.Method != "" {
		method = webhookConfig.Method
	}

	err = agi.webhookSender.SendWebhook(
		agi.ctx,
		webhookConfig.URL,
		method,
		headers,
		payload,
	)

	if err != nil {
		agi.logger.Printf("Error sending webhook for job %s: %v", jobID, err)
	}
}

// Метод для обработки сообщения о завершении синхронного запроса
func (agi *GatewayInstance) HandleSyncStatusFinish() natslib.MsgHandler {
	return func(msg *natslib.Msg) {
		data := &utils.SyncStatus{}
		err := json.Unmarshal(msg.Data, data)

		if err != nil {
			agi.logger.Printf("Error unmarshalling json: %v", err)
			return
		}

		if data.Status != "finished" {
			return
		}

		if data.JobId == "" {
			agi.logger.Printf("Error handling finishing job: job_id is not provided")
			return
		}

		// Проверяем не подхватила ли другая реплика задание на финиш
		redisClient := agi.redis
		lockKey := fmt.Sprintf("transcriber.sync.%s.status.finished", data.JobId)
		ctx := context.Background()
		locker := redislock.New(redisClient)
		lock, err := locker.Obtain(ctx, lockKey, 5*time.Second, nil)

		// Кто-то подхватил, пропускаем
		if err == redislock.ErrNotObtained {
			return
		} else if err != nil {
			agi.logger.Printf("Error obtaining lock for job %v: %v", data.JobId, err)
			return
		}

		defer lock.Release(ctx)

		// Ставим завершающий статус синхронной задачи
		err = agi.databaseContext.JobRepository.UpdateJobStatus(ctx, data.JobId, database.JobStatusFinished, time.Now(), "")

		if err != nil {
			agi.logger.Printf("Error updating job %v status: %v", data.JobId, err)
			return
		}

		agi.logger.Printf("Successfully finished sync job: %v", data.JobId)
	}
}
