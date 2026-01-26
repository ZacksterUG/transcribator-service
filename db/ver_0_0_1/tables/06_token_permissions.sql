CREATE TABLE auth.token_permissions (
    token_id UUID NOT NULL REFERENCES auth.api_tokens(id),
    permission_id INT NOT NULL REFERENCES auth.permissions(id),
    PRIMARY KEY (token_id, permission_id)
);

COMMENT ON TABLE auth.token_permissions IS 'Права, привязанные напрямую к API-токену';
COMMENT ON COLUMN auth.token_permissions.token_id IS 'ID токена';
COMMENT ON COLUMN auth.token_permissions.permission_id IS 'ID права';