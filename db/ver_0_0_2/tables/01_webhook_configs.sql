-- Таблица webhook конфигов
CREATE TABLE jobs.webhook_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID NOT NULL REFERENCES jobs.transcription_jobs(id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    method TEXT NOT NULL DEFAULT 'POST',
    headers JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE jobs.webhook_configs IS 'Конфигурации webhook для задач транскрибации';
COMMENT ON COLUMN jobs.webhook_configs.id IS 'Уникальный ID webhook конфига';
COMMENT ON COLUMN jobs.webhook_configs.job_id IS 'ID задачи транскрибации';
COMMENT ON COLUMN jobs.webhook_configs.url IS 'URL для отправки webhook';
COMMENT ON COLUMN jobs.webhook_configs.method IS 'HTTP метод (POST, PUT)';
COMMENT ON COLUMN jobs.webhook_configs.headers IS 'Дополнительные заголовки';
COMMENT ON COLUMN jobs.webhook_configs.created_at IS 'Время создания конфига';

-- Индекс для быстрого поиска по job_id
CREATE INDEX idx_webhook_configs_job_id ON jobs.webhook_configs(job_id);