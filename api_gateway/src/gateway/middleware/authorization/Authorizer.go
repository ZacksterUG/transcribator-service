package authorization

import (
	"errors"
	"log"

	"github.com/gin-gonic/gin"
	"transcriber-api-gateway/src/gateway/interfaces"
)

// Ошибки авторизации
var (
	ErrNoClaims        = errors.New("no claims found in context")
	ErrMissingUserID   = errors.New("missing USERID header")
	ErrInvalidConfig   = errors.New("invalid Authorizer configuration")
	ErrUnknownAuthType = errors.New("unknown Authorizer type")
)

type AuthType string

const (
	AuthTypeKeycloak     AuthType = "keycloak"
	AuthTypeServiceToken AuthType = "service_token"
)

// Authorizer интерфейс для авторизации
type Authorizer interface {
	AuthType() AuthType
	GetUserID(c *gin.Context) (string, error)
	Middleware() gin.HandlerFunc
	GetClient() *KeycloakClient
}

// AuthConfig конфигурация для создания Authorizer
type AuthConfig struct {
	Type               AuthType
	KeycloakConfig     *KeycloakConfig
	ServiceTokenConfig *ServiceTokenConfig
	Logger             interfaces.Logger
}

// ServiceTokenConfig конфигурация для сервисного токена
type ServiceTokenConfig struct {
	ValidTokens []string
	Logger      interfaces.Logger
}

// ServiceTokenAuthorizer авторизация по сервисному токену
type ServiceTokenAuthorizer struct {
	validTokens map[string]bool
	logger      interfaces.Logger
}

// NewServiceTokenAuthorizer создает авторизатор для сервисных токенов
func NewServiceTokenAuthorizer(config ServiceTokenConfig) *ServiceTokenAuthorizer {
	valid := make(map[string]bool)
	for _, t := range config.ValidTokens {
		valid[t] = true
	}
	return &ServiceTokenAuthorizer{
		validTokens: valid,
		logger:      config.Logger,
	}
}

func (a *ServiceTokenAuthorizer) AuthType() AuthType {
	return AuthTypeServiceToken
}

func (a *ServiceTokenAuthorizer) GetUserID(c *gin.Context) (string, error) {
	userID := c.GetHeader("USERID")
	if userID == "" {
		a.logger.Printf("[ServiceToken] Missing USERID header")
		return "", ErrMissingUserID
	}
	return userID, nil
}

func (a *ServiceTokenAuthorizer) Middleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		token := c.GetHeader("Authorization")
		if token == "" {
			a.logger.Printf("[ServiceToken] Missing Authorization header")
			c.AbortWithStatusJSON(401, gin.H{
				"error": "unauthorized",
			})
			return
		}

		if !a.validTokens[token] {
			a.logger.Printf("[ServiceToken] Invalid token")
			c.AbortWithStatusJSON(401, gin.H{
				"error": "unauthorized",
			})
			return
		}

		userID := c.GetHeader("USERID")
		if userID == "" {
			a.logger.Printf("[ServiceToken] Missing USERID header")
			c.AbortWithStatusJSON(401, gin.H{
				"error": "unauthorized",
			})
			return
		}

		c.Set(ContextKeyUserID, userID)
		a.logger.Printf("[ServiceToken] Request authenticated, user_id: %s", userID)
		c.Next()
	}
}

func (a *ServiceTokenAuthorizer) GetClient() *KeycloakClient {
	return nil
}

// KeycloakAuthorizer авторизация через Keycloak с использованием go-keycloak-middleware
type KeycloakAuthorizer struct {
	client  *KeycloakClient
	builder *KeycloakMiddlewareBuilder
	logger  interfaces.Logger
	config  KeycloakConfig
}

// NewKeycloakAuthorizer создает авторизатор для Keycloak
func NewKeycloakAuthorizer(config KeycloakConfig) *KeycloakAuthorizer {
	if config.Logger == nil {
		config.Logger = interfaces.NewStdLogger(log.Default())
	}

	client := NewKeycloakClient(config)
	builder := NewKeycloakMiddlewareBuilder(config)

	return &KeycloakAuthorizer{
		client:  client,
		builder: builder,
		logger:  config.Logger,
		config:  config,
	}
}

func (a *KeycloakAuthorizer) AuthType() AuthType {
	return AuthTypeKeycloak
}

func (a *KeycloakAuthorizer) GetUserID(c *gin.Context) (string, error) {
	claims := GetClaimsFromContext(c)
	if claims == nil {
		return "", ErrNoClaims
	}
	return claims.Subject, nil
}

// Middleware возвращает middleware для базовой аутентификации
func (a *KeycloakAuthorizer) Middleware() gin.HandlerFunc {
	// Используем builder для создания middleware
	return a.builder.RequireKeycloakAuth()
}

// GetClient возвращает Keycloak клиент
func (a *KeycloakAuthorizer) GetClient() *KeycloakClient {
	return a.client
}

// GetBuilder возвращает middleware builder (для доступа к методам проверки ролей)
func (a *KeycloakAuthorizer) GetBuilder() *KeycloakMiddlewareBuilder {
	return a.builder
}

// CreateAuthorizer создает Authorizer на основе конфигурации
func CreateAuthorizer(config AuthConfig) (Authorizer, error) {
	switch config.Type {
	case AuthTypeServiceToken:
		serviceConfig := config.ServiceTokenConfig
		if serviceConfig == nil || len(serviceConfig.ValidTokens) == 0 {
			return nil, ErrInvalidConfig
		}
		if serviceConfig.Logger == nil {
			serviceConfig.Logger = config.Logger
		}
		return NewServiceTokenAuthorizer(*serviceConfig), nil

	case AuthTypeKeycloak:
		if config.KeycloakConfig == nil {
			return nil, ErrInvalidConfig
		}
		if config.KeycloakConfig.Logger == nil {
			config.KeycloakConfig.Logger = config.Logger
		}
		return NewKeycloakAuthorizer(*config.KeycloakConfig), nil

	default:
		return nil, ErrUnknownAuthType
	}
}
