-- auth.users
CREATE INDEX idx_users_username ON auth.users(username);
CREATE INDEX idx_users_email ON auth.users(email);

-- auth.api_tokens
CREATE INDEX idx_api_tokens_user ON auth.api_tokens(user_id);
CREATE INDEX idx_api_tokens_active ON auth.api_tokens(is_active) WHERE is_active = true;

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