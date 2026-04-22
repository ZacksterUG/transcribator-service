package gateway

import (
	"context"
	"encoding/json"
	"fmt"
	"github.com/nats-io/nats.go/jetstream"
	"log"
	"time"
	"transcriber-api-gateway/src/database"
	"transcriber-api-gateway/src/minio"
	"transcriber-api-gateway/src/nats"
	"transcriber-api-gateway/src/utils"

	"github.com/bsm/redislock"
	"github.com/gin-gonic/gin"
	natslib "github.com/nats-io/nats.go"
	"github.com/redis/go-redis/v9"

	"transcriber-api-gateway/src/gateway/middleware/authorization"
)

type GatewayInstance struct {
	ctx             context.Context
	ginInstance     *gin.Engine
	cfg             GatewayConfig
	authorizer      authorization.Authorizer
	logger          *log.Logger
	storage         *minio.MinIOClient
	redis           *redis.Client
	databaseContext *database.DatabaseContext
	natsContext     *nats.NatsContext
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
) *GatewayInstance {
	g := gin.Default()

	agi := GatewayInstance{
		ctx:             ctx,
		ginInstance:     g,
		cfg:             config,
		authorizer:      Auth,
		logger:          logger,
		storage:         Storage,
		redis:           redisClient,
		databaseContext: databaseContext,
		natsContext:     natsContext,
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

	context := &Context{
		Group:           apiGroup,
		AuthHandler:     *authHandler,
		Logger:          agi.logger,
		Storage:         agi.storage,
		Redis:           agi.redis,
		DatabaseContext: agi.databaseContext,
		NatsContext:     agi.natsContext,
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
