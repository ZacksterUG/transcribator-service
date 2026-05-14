package database

import "errors"

const (
	JobModSync  = "sync"
	JobModAsync = "async"

	JobStatusPending   = "pending"
	JobStatusInProgress = "in_progress"
	JobStatusFinished   = "completed"
	JobStatusFailed     = "failed"
)

var (
	ErrRowDoesNotExists  = errors.New("row does not exists")
	ErrInvalidJobStatus  = errors.New("invalid job status")
)
