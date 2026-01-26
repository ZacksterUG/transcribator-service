CREATE TABLE auth.roles (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT
);

COMMENT ON TABLE auth.roles IS 'Роли пользователей';
COMMENT ON COLUMN auth.roles.id IS 'Внутренний ID роли';
COMMENT ON COLUMN auth.roles.name IS 'Уникальное имя роли';
COMMENT ON COLUMN auth.roles.description IS 'Описание роли';