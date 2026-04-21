-- audit.access_logs
CREATE INDEX idx_access_logs_user ON audit.access_logs(user_id);
CREATE INDEX idx_access_logs_token ON audit.access_logs(token_id);
CREATE INDEX idx_access_logs_time ON audit.access_logs(created_at DESC);
CREATE INDEX idx_access_logs_ip ON audit.access_logs(ip_address);

-- jobs.transcription_jobs
CREATE INDEX idx_jobs_user ON jobs.transcription_jobs(user_id);
CREATE INDEX idx_jobs_mode_status ON jobs.transcription_jobs(mode, status);
CREATE INDEX idx_jobs_created ON jobs.transcription_jobs(created_at DESC);
CREATE INDEX idx_jobs_status ON jobs.transcription_jobs(status);