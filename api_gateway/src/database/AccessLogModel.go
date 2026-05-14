package database

import (
	"time"
)

type AccessLogModel struct {
	ID            int64     `pgx:"id"`
	UserID        *string   `pgx:"user_id"`
	TokenID       *string   `pgx:"token_id"`
	Username      *string   `pgx:"username"`
	Action        string    `pgx:"action"`
	IPAddress     string    `pgx:"ip_address"`
	UserAgent     *string   `pgx:"user_agent"`
	StatusCode    *int      `pgx:"status_code"`
	RequestPath   string    `pgx:"request_path"`
	RequestMethod string    `pgx:"request_method"`
	CreatedAt     time.Time `pgx:"created_at"`
}
