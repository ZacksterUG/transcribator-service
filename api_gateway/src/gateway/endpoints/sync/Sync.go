package sync

import (
	"transcriber-api-gateway/src/gateway"
)

func RegisterAsyncEndpoints(ctx *gateway.Context) {
	authHandler := ctx.AuthHandler
	handler := NewStreamHandler(ctx)
	syncGroup := ctx.Group.Group("/sync")
	{
		syncGroup.GET(
			"/job",
			authHandler.RequireAuth(),
			authHandler.RequireRole("transcriber"),
			handler.HandleWebSocketStream(),
		)
	}
}
