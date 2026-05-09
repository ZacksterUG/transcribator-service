package utils

type SyncStatus struct {
	JobId        string  `json:"job_id"`
	Status       string  `json:"status"`
	ErrorMessage *string `json:"error"`
}

const (
	SyncResponseStatusReady    = "ready"
	SyncResponseStatusAlive    = "alive"
	SyncResponseStatusFinished = "finished"
	SyncResponseStatusFailed   = "failed"
)

type TranscriptionResult struct {
	Text       string `json:"text"`
	IsEndpoint bool   `json:"is_endpoint"`
}

type SyncResponse struct {
	ErrorMessage *string              `json:"message"`
	Result       *TranscriptionResult `json:"result"`
	Error        *bool                `json:"error"`
}
