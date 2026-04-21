package authorization

import (
	"net/http"
	"strings"

	"github.com/gin-gonic/gin"
	keycloak_middleware "github.com/wirnat/go-keycloak-middleware"
	"transcriber-api-gateway/src/gateway/interfaces"
)

const ContextKeyAuthorizer = "Authorizer"
const ContextKeyClaims = "keycloak_claims"
const ContextKeyUserID = "auth_user_id"

// KeycloakMiddlewareBuilder обертка над go-keycloak-middleware
type KeycloakMiddlewareBuilder struct {
	config    keycloak_middleware.KeyCloakConfig
	serverURL string // оригинальный URL с протоколом
	logger    interfaces.Logger
}

// NewKeycloakMiddlewareBuilder создает builder для middleware
func NewKeycloakMiddlewareBuilder(config KeycloakConfig) *KeycloakMiddlewareBuilder {
	// Подготавливаем URL для библиотеки (убираем протокол)
	keycloakIP := strings.TrimPrefix(config.ServerURL, "https://")
	keycloakIP = strings.TrimPrefix(keycloakIP, "http://")
	keycloakIP = strings.TrimSuffix(keycloakIP, "/")

	logger := config.Logger
	if logger == nil {
		logger = interfaces.NewStdLogger(nil)
	}

	return &KeycloakMiddlewareBuilder{
		config: keycloak_middleware.KeyCloakConfig{
			KeyCloakIP:   keycloakIP,
			Realm:        config.Realm,
			ClientID:     config.ClientID,
			ClientSecret: config.ClientSecret,
		},
		serverURL: config.ServerURL,
		logger:    logger,
	}
}

// RequireKeycloakAuth возвращает middleware для базовой авторизации (проверка токена)
func (b *KeycloakMiddlewareBuilder) RequireKeycloakAuth() gin.HandlerFunc {
	return func(c *gin.Context) {
		// Создаем клиент с логгером и полным URL
		client := NewKeycloakClient(KeycloakConfig{
			ServerURL:    b.serverURL,
			Realm:        b.config.Realm,
			ClientID:     b.config.ClientID,
			ClientSecret: b.config.ClientSecret,
			Logger:       b.logger,
		})

		authHeader := c.GetHeader("Authorization")
		if authHeader == "" {
			b.logger.Printf("[Keycloak] No Authorization header provided")
			c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{
				"error":   "unauthorized",
				"message": "Authorization header is required",
			})
			return
		}

		parts := strings.SplitN(authHeader, " ", 2)
		if len(parts) != 2 || strings.ToLower(parts[0]) != "bearer" {
			b.logger.Printf("[Keycloak] Invalid Authorization header format")
			c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{
				"error":   "unauthorized",
				"message": "Authorization header must be in format: Bearer <token>",
			})
			return
		}

		token := parts[1]

		if !client.IsAvailable() {
			b.logger.Printf("[Keycloak] Authentication server unavailable")
			c.AbortWithStatusJSON(http.StatusServiceUnavailable, gin.H{
				"error":   "service_unavailable",
				"message": "Authentication service is temporarily unavailable",
			})
			return
		}

		claims, err := client.ValidateToken(token)
		if err != nil {
			b.logger.Printf("[Keycloak] Token validation failed: %v", err)
			c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{
				"error":   "unauthorized",
				"message": "Invalid or expired token",
			})
			return
		}

		c.Set(ContextKeyClaims, claims)
		c.Set(ContextKeyUserID, claims.Subject)
		b.logger.Printf("[Keycloak] User authenticated: %s", claims.Subject)

		c.Next()
	}
}

// RequireRole возвращает middleware для проверки конкретной роли в Realm
func (b *KeycloakMiddlewareBuilder) RequireRole(role string) gin.HandlerFunc {
	// Создаем middleware для проверки роли
	kcMiddleware := keycloak_middleware.NewKeyCloakMiddleware(b.config)
	return kcMiddleware.RealmAccess(role).GinGuard()
}

// RequireResourceRole возвращает middleware для проверки роли ресурса
func (b *KeycloakMiddlewareBuilder) RequireResourceRole(role string) gin.HandlerFunc {
	kcMiddleware := keycloak_middleware.NewKeyCloakMiddleware(b.config)
	return kcMiddleware.ResourceAccess(role).GinGuard()
}

// RequireRealmAndResourceRole проверяет роль в Realm и доступ к ресурсу
func (b *KeycloakMiddlewareBuilder) RequireRealmAndResourceRole(realmRole, resourceRole string) gin.HandlerFunc {
	kcMiddleware := keycloak_middleware.NewKeyCloakMiddleware(b.config)
	return kcMiddleware.RealmAccess(realmRole).ResourceAccess(resourceRole).GinGuard()
}

// RequireKeycloakAuthLegacy оставлен для совместимости со старым интерфейсом
func RequireKeycloakAuth(authorizer Authorizer) gin.HandlerFunc {
	return func(c *gin.Context) {
		keycloakAuth, ok := authorizer.(*KeycloakAuthorizer)
		if !ok {
			c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{
				"error": "internal_error",
			})
			return
		}

		keycloakAuth.GetBuilder().RequireKeycloakAuth()(c)
	}
}

// GetClaimsFromContext достает claims из контекста Gin
func GetClaimsFromContext(c *gin.Context) *TokenClaims {
	claimsInterface, exists := c.Get(ContextKeyClaims)
	if !exists {
		return nil
	}
	claims, ok := claimsInterface.(*TokenClaims)
	if !ok {
		return nil
	}
	return claims
}

// GetUserIDFromContext достает userID из контекста Gin
func GetUserIDFromContext(c *gin.Context) string {
	if userID, exists := c.Get(ContextKeyUserID); exists {
		if id, ok := userID.(string); ok {
			return id
		}
	}
	return ""
}
