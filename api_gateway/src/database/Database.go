package database

import (
	"context"
	"errors"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
	"log"
	"time"
)

const (
	JobModSync  = "sync"
	JobModAsync = "async"

	JobStatusPending    = "pending"
	JobStatusInProgress = "in_progress"
	JobStatusFinished   = "completed"
	JobStatusFailed     = "failed"
	JobStatusStreaming  = "streaming"
)

type DatabaseContext struct {
	PoolDatabase  *pgxpool.Pool
	JobRepository *JobRepository
}

var ErrRowDoesNotExists = errors.New("row does not exists")
var ErrInvalidJobStatus = errors.New("invalid job status")

type JobModel struct {
	ID                 string     `pgx:"id"`
	UserId             string     `pgx:"user_id"`
	Mode               string     `pgx:"mode"`
	Status             string     `pgx:"status"`
	CreatedAt          time.Time  `pgx:"created_at"`
	StartedAt          *time.Time `pgx:"started_at"`
	StreamingStartedAt *time.Time `pgx:"streaming_started_at"`
	StreamingEndedAt   *time.Time `pgx:"streaming_ended_at"`
	ErrorMessage       *string    `pgx:"error_message"`
}

type JobRepository struct {
	pool   *pgxpool.Pool
	logger *log.Logger
}

func NewJobRepository(pool *pgxpool.Pool, logger *log.Logger) *JobRepository {
	return &JobRepository{pool: pool, logger: logger}
}

func (repo *JobRepository) GetJobById(ctx context.Context, uuid string) (*JobModel, error) {
	queryString := `
	  select j.id,
	  	     j.user_id,
	  	     j.mode,
	  	     j.status,
	  	     j.created_at,
	  	     j.started_at,
	  	     j.streaming_started_at,
	  	     j.streaming_ended_at,
	  	     j.error_message
	    from jobs.transcription_jobs j
       where j.id = $1
	`
	rows, err := repo.pool.Query(ctx, queryString, uuid)

	if err != nil {
		return nil, err
	}

	defer rows.Close()

	row, err := pgx.CollectOneRow(rows, pgx.RowToStructByNameLax[JobModel])

	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, ErrRowDoesNotExists
		}

		return nil, err
	}

	return &row, nil
}

func (repo *JobRepository) CreateAsyncJob(ctx context.Context, userId string) (string, error) {
	query := `
      insert into jobs.transcription_jobs (user_id, mode, status)
      values ($1, 'async', 'pending') 
      returning id, user_id, mode, status
	`

	rows, err := repo.pool.Query(ctx, query, userId)

	if err != nil {
		return "", err
	}

	created, err := pgx.CollectOneRow(
		rows,
		pgx.RowToStructByNameLax[JobModel],
	)

	if err != nil {
		return "", err
	}

	return created.ID, nil
}

func (repo *JobRepository) UpdateJobStatus(
	ctx context.Context,
	jobId string,
	status string,
	completedAt time.Time,
	error_message string,
) error {
	var err error
	var query string

	switch status {
	case JobStatusInProgress:
		query = `
          update jobs.transcription_jobs 
             set status = $1,
                 started_at = $2
           where id = $3
		`
		break
	case JobStatusFinished:
		query = `
		  update jobs.transcription_jobs
			 set status = $1,
		         finished_at = $2
		   where id = $3
        `
		break
	case JobStatusFailed:
		query = `
		  update jobs.transcription_jobs
			 set status = $1,
			     finished_at = $2,
		         error_message = $4
		   where id = $3
        `
		break
	default:
		return ErrInvalidJobStatus
	}

	if status == JobStatusFailed {
		_, err = repo.pool.Exec(ctx, query, status, completedAt, jobId, error_message)
	} else {
		_, err = repo.pool.Exec(ctx, query, status, completedAt, jobId)
	}

	if err != nil {
		return err
	}

	return nil

}
