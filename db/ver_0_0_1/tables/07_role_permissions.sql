CREATE TABLE auth.role_permissions (
    role_id INT NOT NULL REFERENCES auth.roles(id),
    permission_id INT NOT NULL REFERENCES auth.permissions(id),
    PRIMARY KEY (role_id, permission_id)
);

COMMENT ON TABLE auth.role_permissions IS 'Привязка прав к ролям';
COMMENT ON COLUMN auth.role_permissions.role_id IS 'ID роли';
COMMENT ON COLUMN auth.role_permissions.permission_id IS 'ID права';