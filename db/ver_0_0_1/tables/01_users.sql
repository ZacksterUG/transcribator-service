CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE auth.users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username TEXT NOT NULL UNIQUE CHECK (length(username) >= 3),
    email TEXT UNIQUE,
    password_hash TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE auth.users IS 'Пользователи системы';
COMMENT ON COLUMN auth.users.id IS 'Уникальный идентификатор пользователя (UUID)';
COMMENT ON COLUMN auth.users.username IS 'Логин пользователя (уникальный, мин. 3 символа)';
COMMENT ON COLUMN auth.users.email IS 'Электронная почта (опционально, уникальна)';
COMMENT ON COLUMN auth.users.password_hash IS 'Хеш пароля (никогда не открытый текст)';
COMMENT ON COLUMN auth.users.is_active IS 'Флаг активности учётной записи';
COMMENT ON COLUMN auth.users.created_at IS 'Время создания учётной записи';
COMMENT ON COLUMN auth.users.updated_at IS 'Время последнего обновления профиля';