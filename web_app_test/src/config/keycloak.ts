import Keycloak from 'keycloak-js';
import type { User } from '../types/User';

export const keycloakConfig = {
  url: import.meta.env.VITE_KEYCLOAK_URL || 'http://localhost:8080',
  realm: import.meta.env.VITE_KEYCLOAK_REALM || 'dev-realm',
  clientId: import.meta.env.VITE_KEYCLOAK_CLIENT_ID || 'transcriber-web-app',
  redirectUri: window.location.origin,
  publicClient: true,
};

let keycloakInstance: Keycloak | null = null;
let initPromise: Promise<boolean> | null = null;

export function getKeycloak(): Keycloak {
  if (!keycloakInstance) {
    keycloakInstance = new Keycloak(keycloakConfig);
  }
  return keycloakInstance;
}

export async function initKeycloak(): Promise<boolean> {
  if (initPromise) {
    return initPromise;
  }

  initPromise = (async () => {
    const kc = getKeycloak();
    
    try {
      const authenticated = await kc.init({
        pkceMethod: 'S256',
        onLoad: 'check-sso',
        checkLoginIframe: true,
        checkLoginIframeInterval: 30,
      });
      
      if (authenticated) {
        try {
          await kc.loadUserProfile();
        } catch (e) {
          console.warn('Could not load user profile');
        }
      }
      
      return authenticated;
    } catch (error) {
      console.error('Keycloak init error:', error);
      return false;
    }
  })();

  return initPromise;
}

export function login() {
  getKeycloak().login({ redirectUri: window.location.origin });
}

export function logout() {
  getKeycloak().logout({ redirectUri: window.location.origin });
}

export function mapKeycloakToUser(kc: Keycloak): User | null {
  if (!kc.authenticated) return null;
  
  const tokenParsed = kc.tokenParsed as Record<string, unknown> | undefined;
  const clientId = kc.clientId as string;
  
  const clientRoles = (kc.resourceAccess as Record<string, { roles: string[] }>)?.[clientId]?.roles || [];
  const realmRoles = (tokenParsed?.realm_access as { roles: string[] })?.roles || [];
  const roles = [...clientRoles, ...realmRoles];

  return {
    id: kc.subject || '',
    email: tokenParsed?.email as string || '',
    name: (tokenParsed?.name as string) || (tokenParsed?.preferred_username as string) || '',
    roles,
  };
}

export const keycloak = {
  get instance() {
    return getKeycloak();
  },
  get authenticated() {
    return getKeycloak().authenticated;
  },
  login,
  logout,
  loadUserProfile: () => getKeycloak().loadUserProfile(),
  updateToken: (minValidity: number) => getKeycloak().updateToken(minValidity),
  onAuthSuccess: (cb: () => void) => { getKeycloak().onAuthSuccess = cb; },
  onAuthLogout: (cb: () => void) => { getKeycloak().onAuthLogout = cb; },
  onTokenExpired: (cb: () => void) => { getKeycloak().onTokenExpired = cb; },
};