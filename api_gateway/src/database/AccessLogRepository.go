package database

import (
	"context"

	"github.com/jackc/pgx/v5/pgxpool"
)

type AccessLogRepository struct {
	pool *pgxpool.Pool
}

func NewAccessLogRepository(pool *pgxpool.Pool) *AccessLogRepository {
	return &AccessLogRepository{pool: pool}
}

func (repo *AccessLogRepository) CreateAccessLog(
	ctx context.Context,
	userID *string,
	tokenID *string,
	username *string,
	action string,
	ipAddress string,
	userAgent *string,
	statusCode *int,
	requestPath string,
	requestMethod string,
) (int64, error) {
	query := `
		INSERT INTO audit.access_logs (user_id, token_id, username, action, ip_address, user_agent, status_code, request_path, request_method)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
		RETURNING id
	`

	var id int64
	err := repo.pool.QueryRow(
		ctx,
		query,
		userID,
		tokenID,
		username,
		action,
		ipAddress,
		userAgent,
		statusCode,
		requestPath,
		requestMethod,
	).Scan(&id)

	if err != nil {
		return 0, err
	}

	return id, nil
}
