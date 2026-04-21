CREATE TABLE jobs.transcription_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    mode TEXT NOT NULL CHECK (mode IN ('sync', 'async')),
    status TEXT NOT NULL CHECK (status IN (
        'pending', -- Ожидание
        'in_progress', -- В процессе
        'completed', -- Завершен
        'failed', -- Ошибка
        'streaming' -- Стриминг
    )),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    streaming_started_at TIMESTAMPTZ,
    streaming_ended_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    error_message TEXT
);

COMMENT ON TABLE jobs.transcription_jobs IS 'Задачи транскрибации (синхронные и асинхронные)';
COMMENT ON COLUMN jobs.transcription_jobs.id IS 'Уникальный ID задачи';
COMMENT ON COLUMN jobs.transcription_jobs.user_id IS 'Владелец задачи';
COMMENT ON COLUMN jobs.transcription_jobs.mode IS 'Режим: sync или async';
COMMENT ON COLUMN jobs.transcription_jobs.status IS 'Текущий статус задачи';
COMMENT ON COLUMN jobs.transcription_jobs.created_at IS 'Время создания задачи';
COMMENT ON COLUMN jobs.transcription_jobs.started_at IS 'Время начала обработки';
COMMENT ON COLUMN jobs.transcription_jobs.streaming_started_at IS 'Время начала потока (sync)';
COMMENT ON COLUMN jobs.transcription_jobs.streaming_ended_at IS 'Время окончания потока (sync)';
COMMENT ON COLUMN jobs.transcription_jobs.finished_at IS 'Время завершения';
COMMENT ON COLUMN jobs.transcription_jobs.error_message IS 'Сообщение об ошибке';