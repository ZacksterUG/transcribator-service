CREATE TABLE audit.access_logs (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID,
    token_id UUID,
    action TEXT NOT NULL,
    ip_address INET NOT NULL,
    user_agent TEXT,
    status_code INT,
    request_path TEXT NOT NULL,
    request_method TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE audit.access_logs IS 'Журнал аудита всех обращений к API';
COMMENT ON COLUMN audit.access_logs.id IS 'Уникальный ID записи';
COMMENT ON COLUMN audit.access_logs.user_id IS 'ID пользователя (может быть NULL при ошибке аутентификации)';
COMMENT ON COLUMN audit.access_logs.token_id IS 'ID использованного токена';
COMMENT ON COLUMN audit.access_logs.action IS 'Семантическое действие (например: job.create)';
COMMENT ON COLUMN audit.access_logs.ip_address IS 'IP-адрес клиента';
COMMENT ON COLUMN audit.access_logs.user_agent IS 'User-Agent HTTP-заголовок';
COMMENT ON COLUMN audit.access_logs.status_code IS 'HTTP-статус ответа';
COMMENT ON COLUMN audit.access_logs.request_path IS 'Путь HTTP-запроса';
COMMENT ON COLUMN audit.access_logs.request_method IS 'HTTP-метод запроса';
COMMENT ON COLUMN audit.access_logs.created_at IS 'Время запроса';