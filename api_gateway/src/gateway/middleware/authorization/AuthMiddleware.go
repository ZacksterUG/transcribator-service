package authorization

import (
	"errors"
	"net/http"

	"github.com/gin-gonic/gin"
)

// AuthHandler обработчик для авторизации
type AuthHandler struct {
	Authorizer Authorizer
}

// NewAuthHandler создает новый auth handler
func NewAuthHandler(authorizer Authorizer) *AuthHandler {
	return &AuthHandler{Authorizer: authorizer}
}

// RequireAuth middleware требующий аутентификации
func (h *AuthHandler) RequireAuth() gin.HandlerFunc {
	return func(c *gin.Context) {
		if h.Authorizer == nil {
			c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{
				"error":   "internal_error",
				"message": "Authorizer not configured",
			})
			return
		}

		// Используем middleware от Authorizer
		h.Authorizer.Middleware()(c)
		if c.IsAborted() {
			return
		}

		userID, err := h.Authorizer.GetUserID(c)
		if err != nil {
			c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{
				"error":   "unauthorized",
				"message": "Failed to get user ID",
			})
			return
		}

		c.Set(ContextKeyUserID, userID)
		c.Next()
	}
}

// RequireRole middleware требующий конкретной роли
func (h *AuthHandler) RequireRole(role string) gin.HandlerFunc {
	return func(c *gin.Context) {
		// Сначала проверяем авторизацию
		claims := GetClaimsFromContext(c)
		if claims == nil {
			c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{
				"error":   "unauthorized",
				"message": "Authentication required",
			})
			return
		}

		client := h.Authorizer.GetClient()
		if client == nil {
			c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{
				"error": "internal_error",
			})
			return
		}

		if !client.HasRole(claims, role) {
			c.AbortWithStatusJSON(http.StatusForbidden, gin.H{
				"error":         "forbidden",
				"message":       "Insufficient permissions",
				"required_role": role,
			})
			return
		}

		c.Next()
	}
}

// RequireAnyOfRoles middleware требующий любой из указанных ролей
func (h *AuthHandler) RequireAnyOfRoles(roles ...string) gin.HandlerFunc {
	return func(c *gin.Context) {
		claims := GetClaimsFromContext(c)
		if claims == nil {
			c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{
				"error":   "unauthorized",
				"message": "No authentication claims found",
			})
			return
		}

		client := h.Authorizer.GetClient()
		if client == nil {
			c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{
				"error": "internal_error",
			})
			return
		}

		for _, role := range roles {
			if client.HasRole(claims, role) {
				c.Next()
				return
			}
		}

		c.AbortWithStatusJSON(http.StatusForbidden, gin.H{
			"error":          "forbidden",
			"message":        "Insufficient permissions",
			"required_roles": roles,
		})
	}
}

// RequireAllRoles middleware требующий все указанные роли
func (h *AuthHandler) RequireAllRoles(roles ...string) gin.HandlerFunc {
	return func(c *gin.Context) {
		claims := GetClaimsFromContext(c)
		if claims == nil {
			c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{
				"error": "unauthorized",
			})
			return
		}

		client := h.Authorizer.GetClient()
		if client == nil {
			c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{
				"error": "internal_error",
			})
			return
		}

		for _, role := range roles {
			if !client.HasRole(claims, role) {
				c.AbortWithStatusJSON(http.StatusForbidden, gin.H{
					"error":         "forbidden",
					"required_role": role,
					"message":       "Missing required role",
				})
				return
			}
		}

		c.Next()
	}
}

func ContextGetAuthenticator(c *gin.Context) (Authorizer, error) {
	v, exists := c.Get("Authenticator")

	if !exists {
		return nil, errors.New("no authenticator found")
	}

	auth := v.(Authorizer)

	return auth, nil
}
