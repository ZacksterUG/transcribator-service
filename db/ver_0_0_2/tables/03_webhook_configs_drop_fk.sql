-- Удаляем foreign key с job_id для возможности шардирования
ALTER TABLE jobs.webhook_configs DROP CONSTRAINT IF EXISTS webhook_configs_job_id_fkey;

-- Индекс уже есть (01_webhook_configs.sql)