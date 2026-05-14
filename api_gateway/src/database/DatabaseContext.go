package database

import (
	"github.com/jackc/pgx/v5/pgxpool"
)

type DatabaseContext struct {
	PoolDatabase       *pgxpool.Pool
	JobRepository      *JobRepository
	WebhookRepository  *WebhookRepository
	AccessLogRepository *AccessLogRepository
}
