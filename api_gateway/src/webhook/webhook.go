package webhook

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"time"
)

type WebhookSender struct {
	client *http.Client
	logger *log.Logger
}

type WebhookPayload struct {
	JobID       string      `json:"job_id"`
	Status      string      `json:"status"`
	CompletedAt string      `json:"completed_at"`
	Result      interface{} `json:"result,omitempty"`
	Error       string      `json:"error,omitempty"`
}

func NewWebhookSender(logger *log.Logger) *WebhookSender {
	return &WebhookSender{
		client: &http.Client{
			Timeout: 30 * time.Second,
		},
		logger: logger,
	}
}

func (s *WebhookSender) SendWebhook(ctx context.Context, webhookURL, method string, headers map[string]string, payload interface{}) error {
	if webhookURL == "" {
		return nil
	}

	body, err := json.Marshal(payload)
	if err != nil {
		return fmt.Errorf("failed to marshal webhook payload: %w", err)
	}

	req, err := http.NewRequestWithContext(ctx, method, webhookURL, bytes.NewReader(body))
	if err != nil {
		return fmt.Errorf("failed to create webhook request: %w", err)
	}

	req.Header.Set("Content-Type", "application/json")
	for key, value := range headers {
		req.Header.Set(key, value)
	}

	s.logger.Printf("Sending webhook to %s %s", method, webhookURL)

	resp, err := s.client.Do(req)
	if err != nil {
		return fmt.Errorf("failed to send webhook: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 400 {
		respBody, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("webhook returned status %d: %s", resp.StatusCode, string(respBody))
	}

	s.logger.Printf("Webhook sent successfully to %s", webhookURL)
	return nil
}
