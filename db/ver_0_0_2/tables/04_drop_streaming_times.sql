-- Удаляем неиспользуемые поля streaming_started_at и streaming_ended_at
ALTER TABLE jobs.transcription_jobs DROP COLUMN IF EXISTS streaming_started_at;
ALTER TABLE jobs.transcription_jobs DROP COLUMN IF EXISTS streaming_ended_at;