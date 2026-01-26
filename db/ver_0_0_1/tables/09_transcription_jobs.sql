CREATE TABLE jobs.transcription_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    mode TEXT NOT NULL CHECK (mode IN ('sync', 'async')),
    status TEXT NOT NULL CHECK (status IN (
        'queued', -- Ожидание
        'streaming', -- Стриминг
        'processing', -- В процессе
        'completed', -- Завершен
        'failed', -- Ошибка
        'cancelled' -- Отменен
    )),
    audio_file_path TEXT NOT NULL,
    stream_result_path TEXT,
    final_result_path TEXT,
    duration_seconds FLOAT,
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
COMMENT ON COLUMN jobs.transcription_jobs.audio_file_path IS 'Путь к аудиофайлу в MinIO';
COMMENT ON COLUMN jobs.transcription_jobs.stream_result_path IS 'Путь к промежуточному результату (только для sync)';
COMMENT ON COLUMN jobs.transcription_jobs.final_result_path IS 'Путь к финальному результату';
COMMENT ON COLUMN jobs.transcription_jobs.duration_seconds IS 'Длительность аудио в секундах';
COMMENT ON COLUMN jobs.transcription_jobs.created_at IS 'Время создания задачи';
COMMENT ON COLUMN jobs.transcription_jobs.started_at IS 'Время начала обработки';
COMMENT ON COLUMN jobs.transcription_jobs.streaming_started_at IS 'Время начала потока (sync)';
COMMENT ON COLUMN jobs.transcription_jobs.streaming_ended_at IS 'Время окончания потока (sync)';
COMMENT ON COLUMN jobs.transcription_jobs.finished_at IS 'Время завершения';
COMMENT ON COLUMN jobs.transcription_jobs.error_message IS 'Сообщение об ошибке';