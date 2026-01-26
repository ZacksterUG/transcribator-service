CREATE TABLE auth.api_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    token_hash TEXT NOT NULL UNIQUE,
    user_id UUID NOT NULL REFERENCES auth.users(id),
    name TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_used_at TIMESTAMPTZ
);

COMMENT ON TABLE auth.api_tokens IS 'API-токены для аутентификации запросов';
COMMENT ON COLUMN auth.api_tokens.id IS 'Уникальный ID токена';
COMMENT ON COLUMN auth.api_tokens.token_hash IS 'Хеш токена (для безопасного хранения)';
COMMENT ON COLUMN auth.api_tokens.user_id IS 'Владелец токена (пользователь)';
COMMENT ON COLUMN auth.api_tokens.name IS 'Человекочитаемое имя токена';
COMMENT ON COLUMN auth.api_tokens.is_active IS 'Флаг активности токена';
COMMENT ON COLUMN auth.api_tokens.expires_at IS 'Время истечения срока действия (NULL = бессрочно)';
COMMENT ON COLUMN auth.api_tokens.created_at IS 'Время создания токена';
COMMENT ON COLUMN auth.api_tokens.last_used_at IS 'Последнее использование токена';