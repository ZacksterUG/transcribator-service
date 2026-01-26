CREATE TABLE auth.permissions (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT
);

COMMENT ON TABLE auth.permissions IS 'Справочник прав (привилегий)';
COMMENT ON COLUMN auth.permissions.id IS 'Внутренний ID права';
COMMENT ON COLUMN auth.permissions.name IS 'Уникальное имя права (например: transcribe.create)';
COMMENT ON COLUMN auth.permissions.description IS 'Человекочитаемое описание права';