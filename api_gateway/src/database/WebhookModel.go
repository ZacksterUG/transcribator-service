package database

import (
	"time"
)

type WebhookConfigModel struct {
	ID        string    `pgx:"id"`
	JobID     string    `pgx:"job_id"`
	URL       string    `pgx:"url"`
	Method    string    `pgx:"method"`
	Headers   string    `pgx:"headers"`
	CreatedAt time.Time `pgx:"created_at"`
}
