package accessLogging

import (
	"context"

	"github.com/gin-gonic/gin"
	"transcriber-api-gateway/src/database"
	"transcriber-api-gateway/src/gateway/middleware/authorization"
)

type AccessLoggingMiddleware struct {
	repository *database.AccessLogRepository
	logger     interface {
		Printf(format string, v ...interface{})
	}
}

type responseWriter struct {
	gin.ResponseWriter
	statusCode *int
}

func (w *responseWriter) WriteHeader(code int) {
	*w.statusCode = code
	w.ResponseWriter.WriteHeader(code)
}

func NewAccessLoggingMiddleware(
	repository *database.AccessLogRepository,
	logger interface {
		Printf(format string, v ...interface{})
	},
) *AccessLoggingMiddleware {
	return &AccessLoggingMiddleware{
		repository: repository,
		logger:     logger,
	}
}

func (m *AccessLoggingMiddleware) Handler(action string) gin.HandlerFunc {
	return func(c *gin.Context) {
		wrapper := &responseWriter{
			ResponseWriter: c.Writer,
			statusCode:     new(int),
		}
		*wrapper.statusCode = 200
		c.Writer = wrapper

		c.Next()

		go func() {
			var userIDPtr *string
			userID := authorization.GetUserIDFromContext(c)
			if userID != "" {
				userIDPtr = &userID
			}

			var tokenIDPtr *string
			var usernamePtr *string
			claims := authorization.GetClaimsFromContext(c)
			if claims != nil {
				if claims.ID != "" {
					tokenIDPtr = &claims.ID
				}
				if claims.PreferredUsername != "" {
					usernamePtr = &claims.PreferredUsername
				}
			}

			var statusCodePtr *int
			if wrapper.statusCode != nil {
				statusCodePtr = wrapper.statusCode
			}

			ip := c.ClientIP()
			userAgent := c.GetHeader("User-Agent")

			var userAgentPtr *string
			if userAgent != "" {
				userAgentPtr = &userAgent
			}

			ctx := context.Background()

			_, err := m.repository.CreateAccessLog(
				ctx,
				userIDPtr,
				tokenIDPtr,
				usernamePtr,
				action,
				ip,
				userAgentPtr,
				statusCodePtr,
				c.Request.URL.Path,
				c.Request.Method,
			)

			if err != nil {
				m.logger.Printf("Failed to create access log: %v", err)
			}
		}()
	}
}
