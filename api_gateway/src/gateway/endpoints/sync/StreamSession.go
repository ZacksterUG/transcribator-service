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
	"log"
	"sync"
	"time"
	"transcriber-api-gateway/src/utils"
)

type StreamSession struct {
	jobId      string
	conn       *websocket.Conn
	nats       *nats.Conn
	logger     *log.Logger
	statusCh   chan utils.SyncStatus
	responseCh chan utils.SyncResponse
	finishCh   chan struct{}
	cancel     context.CancelFunc
	ctx        context.Context
	wg         sync.WaitGroup
	// Подписки NATS для корректной отписки
	statusSub   *nats.Subscription
	responseSub *nats.Subscription
	initSub     *nats.Subscription
}

func (h *StreamHandler) newStreamSession(parentCtx context.Context, jobId string, conn *websocket.Conn) (*StreamSession, error) {
	ctx, cancel := context.WithCancel(parentCtx)

	s := &StreamSession{
		jobId:      jobId,
		conn:       conn,
		nats:       h.apiCtx.NatsContext.NatsCore,
		logger:     h.apiCtx.Logger,
		statusCh:   make(chan utils.SyncStatus, 1),
		responseCh: make(chan utils.SyncResponse, 10), // буфер для предотвращения блокировок
		finishCh:   make(chan struct{}),
		cancel:     cancel,
		ctx:        ctx,
	}

	// Подписываемся на NATS-топики
	if err := s.subscribeNATS(); err != nil {
		cancel()
		return nil, fmt.Errorf("subscribe failed: %w", err)
	}

	// Отправляем инициализацию
	if err := s.sendInit(); err != nil {
		s.unsubscribeNATS()
		cancel()
		return nil, fmt.Errorf("init failed: %w", err)
	}

	// Ждём подтверждения готовности
	if err := s.waitForReady(); err != nil {
		s.Close()
		return nil, fmt.Errorf("ready wait failed: %w", err)
	}

	return s, nil
}

func (s *StreamSession) subscribeNATS() error {
	var err error

	// Подписка на статусы
	s.statusSub, err = s.nats.Subscribe(
		fmt.Sprintf("transcriber.sync.status.%s", s.jobId),
		s.handleStatusMessage,
	)
	if err != nil {
		return fmt.Errorf("subscribe status: %w", err)
	}

	// Подписка на ответы транскрайбера
	s.responseSub, err = s.nats.Subscribe(
		fmt.Sprintf("transcriber.sync.response.%s", s.jobId),
		s.handleResponseMessage,
	)
	if err != nil {
		// При ошибке второй подписки — отменяем первую
		_ = s.statusSub.Unsubscribe()
		s.statusSub = nil
		return fmt.Errorf("subscribe response: %w", err)
	}

	// Опционально: настройка очередей, если нужно
	// s.statusSub.SetPendingLimits(1000, 10*1024*1024) // 1000 msgs, 10MB

	return nil
}

func (s *StreamSession) unsubscribeNATS() {
	// Отписываемся в обратном порядке — не критично, но логично
	if s.responseSub != nil && s.responseSub.IsValid() {
		if err := s.responseSub.Unsubscribe(); err != nil {
			s.logger.Printf("job %s: failed to unsubscribe from response: %v", s.jobId, err)
		}
		s.responseSub = nil
	}

	if s.statusSub != nil && s.statusSub.IsValid() {
		if err := s.statusSub.Unsubscribe(); err != nil {
			s.logger.Printf("job %s: failed to unsubscribe from status: %v", s.jobId, err)
		}
		s.statusSub = nil
	}

	if s.initSub != nil && s.initSub.IsValid() {
		if err := s.initSub.Unsubscribe(); err != nil {
			s.logger.Printf("job %s: failed to unsubscribe from init: %v", s.jobId, err)
		}
		s.initSub = nil
	}

	s.logger.Printf("job %s: unsubscribed from NATS topics", s.jobId)
}

func (s *StreamSession) Start() {
	s.wg.Add(2)

	// Ping-монитор
	go func() {
		defer s.wg.Done()
		s.runPingLoop()
	}()

	// Отправка ответов клиенту
	go func() {
		defer s.wg.Done()
		s.forwardResponsesToClient()
	}()

	// Отправляем статус "ready" клиенту только после успешной инициализации
	_ = wsjson.Write(s.ctx, s.conn, gin.H{"status": "ready"})
	s.logger.Printf("job %s ready for streaming", s.jobId)
}

func (s *StreamSession) Close() {
	s.cancel()
	s.unsubscribeNATS()
	s.wg.Wait()
	_ = s.conn.Close(websocket.StatusNormalClosure, "session closed")
}

func (h *StreamHandler) handleReadError(logger *log.Logger, err error, msgType websocket.MessageType, session *StreamSession) {
	// Отправляем сигнал завершения в транскрайбер
	finishPayload := map[string]bool{"finish": true}
	if data, err := json.Marshal(finishPayload); err == nil {
		_ = session.nats.Publish(
			fmt.Sprintf("transcriber.sync.processing.%s", session.jobId),
			data,
		)
	}

	// Логируем с детализацией
	switch {
	case websocket.CloseStatus(err) == websocket.StatusNormalClosure:
		logger.Printf("client closed connection normally")
	case websocket.CloseStatus(err) == websocket.StatusGoingAway:
		logger.Printf("client went away")
	case errors.Is(err, context.DeadlineExceeded):
		logger.Printf("read timeout exceeded")
	default:
		logger.Printf("read error: %v (type: %v)", err, msgType)
	}
}

func (s *StreamSession) runPingLoop() {
	ticker := time.NewTicker(15 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-s.ctx.Done():
			return
		case <-ticker.C:
			pingCtx, cancel := context.WithTimeout(s.ctx, 10*time.Second)
			err := s.conn.Ping(pingCtx)
			cancel()

			if err != nil {
				s.logger.Printf("ping failed for job %s: %v", s.jobId, err)
				_ = s.conn.Close(websocket.StatusInternalError, "ping failed")
				return
			}
		}
	}
}

func (s *StreamSession) sendInit() error {
	data := gin.H{"job_id": s.jobId}
	dataBinary, err := json.Marshal(&data)
	if err != nil {
		return fmt.Errorf("marshal init data: %w", err)
	}

	if err := s.nats.Publish("transcriber.sync.init", dataBinary); err != nil {
		return fmt.Errorf("publish init: %w", err)
	}

	s.logger.Printf("job %s: init sent", s.jobId)
	return nil
}

func (s *StreamSession) waitForReady() error {
	ctx, cancel := context.WithTimeout(s.ctx, 10*time.Second)
	defer cancel()

	select {
	case status := <-s.statusCh:
		switch status.Status {
		case utils.SyncResponseStatusReady:
			s.logger.Printf("job %s: backend ready", s.jobId)
			return nil
		case utils.SyncResponseStatusFailed:
			errorMessage := "unknown error"
			if status.ErrorMessage != nil {
				errorMessage = *status.ErrorMessage
			}
			return fmt.Errorf("backend init failed: %s", errorMessage)
		default:
			// Неожиданный статус — пробуем продолжить, но логируем
			s.logger.Printf("job %s: unexpected status '%s', continuing...", s.jobId, status.Status)
			return nil
		}
	case <-ctx.Done():
		return fmt.Errorf("timeout waiting for ready: %w", ctx.Err())
	case <-s.ctx.Done():
		return fmt.Errorf("session cancelled: %w", s.ctx.Err())
	}
}

func (s *StreamSession) forwardResponsesToClient() {
	for {
		select {
		case <-s.ctx.Done():
			s.logger.Printf("job %s: response forwarder stopped (context done)", s.jobId)
			return

		case response := <-s.responseCh:
			if err := wsjson.Write(s.ctx, s.conn, gin.H{
				"type": "response",
				"data": response,
			}); err != nil {
				s.logger.Printf("job %s: failed to write response to client: %v", s.jobId, err)
				// Не прерываем цикл — возможно, ошибка временная
				// Но можно добавить счётчик ошибок для graceful shutdown
				continue
			}

		case status := <-s.statusCh:
			// Обработка статусов в реальном времени (не только при инициализации)
			if status.Status == utils.SyncResponseStatusFinished || status.Status == utils.SyncResponseStatusFailed {
				s.logger.Printf("job %s: received terminal status '%s'", s.jobId, status.Status)
				if status.Status == utils.SyncResponseStatusFailed && status.ErrorMessage != nil {
					_ = wsjson.Write(s.ctx, s.conn, gin.H{
						"type":  "error",
						"error": status.ErrorMessage,
					})
				}
				return // Завершаем горутину — сессия окончена
			}
			// Промежуточные статусы можно логировать или отправлять клиенту при необходимости
		}
	}
}

func (s *StreamSession) handleStatusMessage(msg *nats.Msg) {
	var status utils.SyncStatus
	if err := json.Unmarshal(msg.Data, &status); err != nil {
		s.logger.Printf("job %s: unmarshal status failed: %v", s.jobId, err)
		return
	}

	select {
	case s.statusCh <- status:
		// Успешно отправили в канал
	case <-s.ctx.Done():
		// Контекст отменён — не блокируем горутину NATS
		s.logger.Printf("job %s: context done, dropping status message", s.jobId)
	}
}

func (s *StreamSession) handleResponseMessage(msg *nats.Msg) {
	var resp utils.SyncResponse
	if err := json.Unmarshal(msg.Data, &resp); err != nil {
		s.logger.Printf("job %s: unmarshal response failed: %v", s.jobId, err)
		return
	}

	select {
	case s.responseCh <- resp:
	case <-s.ctx.Done():
		s.logger.Printf("job %s: context done, dropping response message", s.jobId)
	}
}
