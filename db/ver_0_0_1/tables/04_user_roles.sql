CREATE TABLE auth.user_roles (
    user_id UUID NOT NULL REFERENCES auth.users(id),
    role_id INT NOT NULL REFERENCES auth.roles(id),
    PRIMARY KEY (user_id, role_id)
);

COMMENT ON TABLE auth.user_roles IS 'Назначение ролей пользователям';
COMMENT ON COLUMN auth.user_roles.user_id IS 'ID пользователя';
COMMENT ON COLUMN auth.user_roles.role_id IS 'ID роли';