export const oidcConfig = {
  authority: import.meta.env.VITE_KEYCLOAK_URL || 'http://localhost:8080',
  client_id: import.meta.env.VITE_KEYCLOAK_CLIENT_ID || 'transcriber_web_test',
  redirect_uri: import.meta.env.VITE_KEYCLOAK_REDIRECT_URI || 'http://localhost:5173',
  response_type: 'code',
  scope: 'openid profile email',
  automaticSilentRenew: true,
  loadUserInfo: true,
};