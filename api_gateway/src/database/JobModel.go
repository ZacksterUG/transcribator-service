package database

import (
	"time"
)

type JobModel struct {
	ID          string     `pgx:"id"`
	UserId      string     `pgx:"user_id"`
	Mode        string     `pgx:"mode"`
	Status      string     `pgx:"status"`
	CreatedAt   time.Time  `pgx:"created_at"`
	StartedAt   *time.Time `pgx:"started_at"`
	ErrorMessage *string   `pgx:"error_message"`
}
