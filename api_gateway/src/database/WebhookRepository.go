package database

import (
	"context"
	"errors"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

type WebhookRepository struct {
	pool *pgxpool.Pool
}

func NewWebhookRepository(pool *pgxpool.Pool) *WebhookRepository {
	return &WebhookRepository{pool: pool}
}

func (repo *WebhookRepository) CreateWebhookConfig(
	ctx context.Context,
	jobID string,
	url string,
	method string,
	headers string,
) (string, error) {
	query := `
		INSERT INTO jobs.webhook_configs (job_id, url, method, headers)
		VALUES ($1, $2, $3, $4)
		RETURNING id
	`

	var id string
	err := repo.pool.QueryRow(ctx, query, jobID, url, method, headers).Scan(&id)

	if err != nil {
		return "", err
	}

	return id, nil
}

func (repo *WebhookRepository) GetWebhookConfigByJobID(ctx context.Context, jobID string) (*WebhookConfigModel, error) {
	query := `
		SELECT id, job_id, url, method, headers, created_at
		FROM jobs.webhook_configs
		WHERE job_id = $1
	`

	rows, err := repo.pool.Query(ctx, query, jobID)

	if err != nil {
		return nil, err
	}

	defer rows.Close()

	row, err := pgx.CollectOneRow(rows, pgx.RowToStructByNameLax[WebhookConfigModel])

	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, ErrRowDoesNotExists
		}

		return nil, err
	}

	return &row, nil
}
