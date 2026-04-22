package sync

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"github.com/coder/websocket"
	"github.com/coder/websocket/wsjson"
	"github.com/gin-gonic/gin"
	"github.com/nats-io/nats.go"
	"net/http"
	"sync"
	"time"
	"transcriber-api-gateway/src/gateway"
	"transcriber-api-gateway/src/gateway/endpoints"
	"transcriber-api-gateway/src/utils"
)

func RegisterAsyncEndpoints(ctx *gateway.Context) {
	authHandler := ctx.AuthHandler

	syncGroup := ctx.Group.Group("/sync")
	{
		syncGroup.GET(
			"/job",
			authHandler.RequireAuth(),
			authHandler.RequireRole("transcriber"),
			webSocketStreaming(ctx),
		)
	}
}

func pingConnection(ctx context.Context, apiCtx *gateway.Context, ginCtx *gin.Context, conn *websocket.Conn) {
	ticker := time.NewTicker(15 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			pingCtx, pingCancel := context.WithTimeout(ginCtx.Request.Context(), 10*time.Second)
			err := conn.Ping(pingCtx)
			pingCancel()

			if err != nil {
				conn.Close(websocket.StatusInternalError, "ping failed")
				userId, _ := apiCtx.AuthHandler.Authorizer.GetUserID(ginCtx)
				apiCtx.Logger.Printf("ping failed to user %v", userId)
				return
			}
		}
	}
}

func webSocketStreaming(apiCtx *gateway.Context) gin.HandlerFunc {
	return func(c *gin.Context) {
		conn, err := websocket.Accept(c.Writer, c.Request, &websocket.AcceptOptions{InsecureSkipVerify: true})
		logger := apiCtx.Logger

		if err != nil {
			endpoints.SendErrorMessage(c, http.StatusInternalServerError, err.Error())
			return
		}

		defer conn.Close(websocket.StatusNormalClosure, "closed")

		pingCtx, pingCancel := context.WithCancel(context.Background())
		go pingConnection(pingCtx, apiCtx, c, conn)
		defer pingCancel()

		userId, err := apiCtx.AuthHandler.Authorizer.GetUserID(c)

		if err != nil {
			logger.Printf("get user id failed: %v", err)
			return
		}

		jobId, err := apiCtx.DatabaseContext.JobRepository.CreateSyncJob(c.Request.Context(), userId)

		if err != nil {
			logger.Printf("create job failed: %v", err)
			return
		}

		natsCore := apiCtx.NatsContext.NatsCore

		data := gin.H{
			"job_id": jobId,
		}
		dataBinary, err := json.Marshal(&data)

		if err != nil {
			logger.Printf("marshal data failed: %v", err)
			return
		}

		isReadyChan := make(chan bool)

		ctxTimeout, cancelFn := context.WithTimeout(c.Request.Context(), time.Second*10)
		defer cancelFn()

		statusQueue, err := natsCore.Subscribe(
			fmt.Sprintf("transcriber.sync.status.%v", jobId),
			handleStatusChange(ctxTimeout, jobId, isReadyChan),
		)

		if err != nil {
			logger.Printf("subscribe to status queue failed: %v", err)
			return
		}

		receiveChannel := make(chan utils.SyncResponse)

		receiveQueue, err := natsCore.Subscribe(
			fmt.Sprintf("transcriber.sync.response.%v.", jobId),
			handleSycMessages(apiCtx, jobId, receiveChannel),
		)

		if err != nil {
			logger.Printf("subscribe to response queue status failed: %v", err)
			return
		}

		defer func() {
			logger.Printf("unsubscribe from queue job: %v", jobId)
			statusQueue.Unsubscribe()
			receiveQueue.Unsubscribe()
		}()

		err = natsCore.Publish("transcriber.sync.init", dataBinary)

		if err != nil {
			logger.Printf("Failed to initialise stream: %v", err)
			return
		}

		select {
		case ready := <-isReadyChan:
			if !ready {
				logger.Printf("Failed to initialise stream: didnt receive init event")
				return
			}
		case <-ctxTimeout.Done():
			logger.Printf("Failed to initialise stream: timeout")
			return
		}

		logger.Printf("job %v ready for streaming", jobId)

		wsjson.Write(c.Request.Context(), conn, gin.H{
			"status": "ready",
		})

		wg := sync.WaitGroup{}
		wg.Add(1)

		go func() {
			defer wg.Done()

			for {
				select {
				case <-pingCtx.Done():
					return
				case response := <-receiveChannel:
					wsjson.Write(c.Request.Context(), conn, gin.H{
						"type": "response",
						"data": response,
					})
				}
			}
		}()

		for {
			loopCtx, cancelLoop := context.WithTimeout(pingCtx, 10*time.Second)
			msgType, message, err := conn.Read(loopCtx)

			cancelLoop()

			if err != nil {
				if websocket.CloseStatus(err) == websocket.StatusNormalClosure ||
					websocket.CloseStatus(err) == websocket.StatusGoingAway {
					logger.Printf("%s closed the connection with status code '%d", msgType, message)
				} else if errors.Is(err, context.DeadlineExceeded) {
					logger.Printf("%s deadline exceeded with status code '%d'", msgType, message)
				} else {
					logger.Printf("%s read message failed with status code '%d'", msgType, message)
				}

				break
			}

			// TODO получить аудиобайты, преобразовать в вид принимаемый очередью и отправить

		}

		wg.Wait()
	}
}

func handleStatusChange(ctx context.Context, jobId string, isReadyChan chan bool) func(msg *nats.Msg) {
	return func(msg *nats.Msg) {
		data := &utils.SyncStatus{}
		err := json.Unmarshal(msg.Data, data)

		if err != nil {
			ctx.Done()
			return
		}

		if data.Status == utils.SyncResponseStatusReady {
			isReadyChan <- true
			return
		}
	}
}

func handleSycMessages(apiCtx *gateway.Context, jobId string, receiveChan chan utils.SyncResponse) func(msg *nats.Msg) {
	return func(msg *nats.Msg) {
		data := &utils.SyncResponse{}
		logger := apiCtx.Logger
		err := json.Unmarshal(msg.Data, data)

		if err != nil {
			logger.Printf("unmarshal data failed: %v, job id: %v", err, jobId)
			return
		}

		receiveChan <- *data
	}
}
