package sync

import (
	"context"
	"encoding/json"
	"fmt"
	"github.com/coder/websocket"
	"github.com/gin-gonic/gin"
	"net/http"
	"time"
	"transcriber-api-gateway/src/gateway/endpoints"

	"transcriber-api-gateway/src/gateway"
)

// StreamHandler инкапсулирует всю логику стриминга
type StreamHandler struct {
	apiCtx       *gateway.Context
	pingInterval time.Duration
	pingTimeout  time.Duration
	initTimeout  time.Duration
}

func NewStreamHandler(apiCtx *gateway.Context) *StreamHandler {
	return &StreamHandler{
		apiCtx:       apiCtx,
		pingInterval: 15 * time.Second,
		pingTimeout:  10 * time.Second,
		initTimeout:  10 * time.Second,
	}
}

func (h *StreamHandler) HandleWebSocketStream() gin.HandlerFunc {
	return func(c *gin.Context) {
		logger := h.apiCtx.Logger

		// 1. Устанавливаем WebSocket-соединение
		conn, err := websocket.Accept(c.Writer, c.Request, &websocket.AcceptOptions{InsecureSkipVerify: true})
		if err != nil {
			endpoints.SendErrorMessage(c, http.StatusInternalServerError, err.Error())
			return
		}
		defer conn.Close(websocket.StatusNormalClosure, "closed")

		// 2. Получаем пользователя и создаём задачу
		userId, err := h.apiCtx.AuthHandler.Authorizer.GetUserID(c)
		if err != nil {
			logger.Printf("get user id failed: %v", err)
			return
		}

		jobId, err := h.apiCtx.DatabaseContext.JobRepository.CreateSyncJob(c.Request.Context(), userId)
		if err != nil {
			logger.Printf("create job failed: %v", err)
			return
		}

		// 3. Инициализируем сессию
		session, err := h.newStreamSession(c.Request.Context(), jobId, conn)
		if err != nil {
			logger.Printf("failed to init session: %v", err)
			return
		}
		defer session.Close()

		// 4. Запускаем фоновые процессы
		session.Start()

		// 5. Обрабатываем входящие сообщения от клиента
		h.handleClientMessages(c, session)
	}
}

func (h *StreamHandler) handleClientMessages(c *gin.Context, session *StreamSession) {
	logger := h.apiCtx.Logger

	for {
		loopCtx, cancel := context.WithTimeout(session.ctx, 10*time.Second)
		msgType, message, err := session.conn.Read(loopCtx)
		cancel()

		if err != nil {
			h.handleReadError(logger, err, msgType, session)
			break
		}

		if err := h.processAudioMessage(session, message); err != nil {
			logger.Printf("process audio failed: %v", err)
			continue
		}
	}
}

func (h *StreamHandler) processAudioMessage(session *StreamSession, raw []byte) error {
	var audioMsg struct {
		Bytes string `json:"bytes"`
	}
	if err := json.Unmarshal(raw, &audioMsg); err != nil {
		return fmt.Errorf("parse failed: %w", err)
	}

	payload := map[string]string{"bytes": audioMsg.Bytes}
	data, err := json.Marshal(payload)
	if err != nil {
		return fmt.Errorf("marshal failed: %w", err)
	}

	return session.nats.Publish(
		fmt.Sprintf("transcriber.sync.processing.%s", session.jobId),
		data,
	)
}
