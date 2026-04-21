package endpoints

import (
	"github.com/gin-gonic/gin"
	"net/http"
	"transcriber-api-gateway/src/gateway"
)

func RegisterAuthTest(ctx *gateway.Context) {
	utilGroup := ctx.Group.Group("/auth-test")
	{
		utilGroup.GET("/check", CheckHandler(ctx))
		utilGroup.GET(
			"/need-auth",
			ctx.AuthHandler.RequireAuth(),
			NeedAuthHandler(ctx),
		)
	}
}

func CheckHandler(apiCtx *gateway.Context) gin.HandlerFunc {
	return func(c *gin.Context) {
		apiCtx.Logger.Print(apiCtx.AuthHandler.Authorizer.AuthType())

		c.JSON(200, gin.H{
			"message": "ok",
		})
	}
}

func NeedAuthHandler(apiCtx *gateway.Context) gin.HandlerFunc {
	return func(c *gin.Context) {
		authorizer := apiCtx.AuthHandler.Authorizer

		val, _ := authorizer.GetUserID(c)

		c.JSON(http.StatusOK, gin.H{
			"message": "ok",
			"data":    val,
		})
	}
}
