-- add username to access_logs
ALTER TABLE audit.access_logs ADD COLUMN IF NOT EXISTS username TEXT;

COMMENT ON COLUMN audit.access_logs.username IS 'Имя пользователя или client_id (для service account)';