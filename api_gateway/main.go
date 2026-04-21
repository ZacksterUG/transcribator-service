package main

import (
	"context"
	"log"
	"os"
	"strconv"
	"strings"
	"transcriber-api-gateway/src/database"
	"transcriber-api-gateway/src/gateway/endpoints"
	"transcriber-api-gateway/src/gateway/endpoints/async"

	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/joho/godotenv"
	"github.com/redis/go-redis/v9"

	"transcriber-api-gateway/src/gateway"
	"transcriber-api-gateway/src/gateway/interfaces"
	"transcriber-api-gateway/src/gateway/middleware/authorization"
	"transcriber-api-gateway/src/minio"
	"transcriber-api-gateway/src/nats"
)

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

func getEnvBool(key string, defaultValue bool) bool {
	if value := os.Getenv(key); value != "" {
		if b, _ := parseBool(key, value); b {
			return b
		}
	}
	return defaultValue
}

func parseBool(key, value string) (bool, error) {
	switch strings.ToLower(value) {
	case "true", "1", "yes":
		return true, nil
	case "false", "0", "no":
		return false, nil
	default:
		return false, nil
	}
}

func getEnvList(key string) []string {
	value := os.Getenv(key)
	if value == "" {
		return nil
	}
	tokens := strings.Split(value, ",")
	result := make([]string, 0, len(tokens))
	for _, t := range tokens {
		t = strings.TrimSpace(t)
		if t != "" {
			result = append(result, t)
		}
	}
	return result
}

func InitiateHandlers() []gateway.RegisterHandler {
	return []gateway.RegisterHandler{
		endpoints.RegisterRoutes,
		endpoints.RegisterAuthTest,
		async.RegisterAsyncEndpoints,
	}
}

func InitiateRedis() *redis.Client {
	host := getEnv("REDIS_HOST", "localhost")
	port := getEnv("REDIS_PORT", "6379")
	password := getEnv("REDIS_PASSWORD", "")
	dbNumStr, _ := strconv.Atoi(getEnv("REDIS_DB", "0"))

	redisDB := redis.NewClient(&redis.Options{
		Addr:     host + ":" + port,
		Password: password,
		DB:       dbNumStr,
	})

	return redisDB
}

func InitiateNats() (*nats.NatsContext, error) {
	host := getEnv("NATS_SERVER", "localhost")
	requestAsyncTopic := getEnv("ASYNC_REQUEST_TOPIC", "transcriber.async.request")
	responseAsyncTopic := getEnv("ASYNC_RESPONSE_TOPIC", "transcriber.async.response")

	nc, err := nats.NewNatsConn(host, requestAsyncTopic, responseAsyncTopic)

	if err != nil {
		return nil, err
	}

	return nc, nil
}

func InitiateDatabase(ctx context.Context) (*pgxpool.Pool, error) {
	host := getEnv("POSTGRESQL_HOST", "localhost")
	port := getEnv("POSTGRESQL_PORT", "5432")
	user := getEnv("POSTGRESQL_USER", "postgres")
	password := getEnv("POSTGRESQL_PASSWORD", "postgres")
	db := getEnv("POSTGRESQL_DB", "transcription_db")

	strBuilder := strings.Builder{}
	strBuilder.WriteString("postgres://")
	strBuilder.WriteString(user)
	strBuilder.WriteString(":")
	strBuilder.WriteString(password)
	strBuilder.WriteString("@")
	strBuilder.WriteString(host)
	strBuilder.WriteString(":")
	strBuilder.WriteString(port)
	strBuilder.WriteString("/")
	strBuilder.WriteString(db)

	dsn := strBuilder.String()

	pool, err := pgxpool.New(ctx, dsn)

	return pool, err
}

func main() {
	godotenv.Overload()
	ctx := context.Background()
	logger := log.New(os.Stdout, "[Gateway] ", log.Ldate|log.Ltime|log.Lshortfile)

	authType := authorization.AuthType(getEnv("AUTH_TYPE", "keycloak"))

	minioClient, err := minio.NewMinIOClient(
		getEnv("MINIO_URL", ""),
		getEnv("MINIO_USER", ""),
		getEnv("MINIO_PASSWORD", ""),
		getEnv("MINIO_BUCKET", ""),
	)

	if err != nil {
		logger.Fatal(err)
	}

	db, err := InitiateDatabase(ctx)

	if err != nil {
		logger.Fatal(err)
	}

	defer db.Close()

	logger.Print("authType:", authType)
	redisDB := InitiateRedis()
	status := redisDB.Ping(ctx)

	_, err = status.Result()

	if err != nil {
		logger.Fatal(err)
	}

	nats, err := InitiateNats()

	if err != nil {
		logger.Fatal(err)
	}

	defer nats.Close()

	if err != nil {
		logger.Fatal(err)
	}

	authConfig := authorization.AuthConfig{
		Type:   authType,
		Logger: interfaces.NewStdLogger(logger),
	}

	switch authType {
	case authorization.AuthTypeServiceToken:
		authConfig.ServiceTokenConfig = &authorization.ServiceTokenConfig{
			ValidTokens: getEnvList("SERVICE_TOKENS"),
		}

	case authorization.AuthTypeKeycloak:
		authConfig.KeycloakConfig = &authorization.KeycloakConfig{
			ServerURL: getEnv("KEYCLOAK_SERVER_URL", "http://keycloak:8080"),
			Realm:     getEnv("KEYCLOAK_REALM", "master"),
			ClientID:  getEnv("KEYCLOAK_CLIENT_ID", "api-gateway"),
			VerifySSL: getEnvBool("KEYCLOAK_VERIFY_SSL", true),
		}
	}

	authorizer, err := authorization.CreateAuthorizer(authConfig)

	if err != nil {
		logger.Fatal(err)
	}

	jobRepo := database.NewJobRepository(db, logger)

	dbContext := &database.DatabaseContext{
		PoolDatabase:  db,
		JobRepository: jobRepo,
	}

	gatewayApp := gateway.Gateway(
		ctx,
		logger,
		authorizer,
		minioClient,
		redisDB,
		gateway.GatewayConfig{
			Port: getEnv("GATEWAY_PORT", "10000"),
		},
		dbContext,
		nats,
	)

	gatewayApp.Setup(InitiateHandlers())
	gatewayApp.Start()
}
