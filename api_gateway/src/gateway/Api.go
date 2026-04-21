package gateway

import (
	"context"
	"encoding/json"
	"github.com/nats-io/nats.go/jetstream"
	"log"
	"time"
	"transcriber-api-gateway/src/database"
	"transcriber-api-gateway/src/minio"
	"transcriber-api-gateway/src/nats"

	"github.com/gin-gonic/gin"
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

	err := agi.natsContext.Subscribe(agi.ctx, agi.HandleAsyncResponses())

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
