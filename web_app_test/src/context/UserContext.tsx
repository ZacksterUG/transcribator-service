import { createContext, useState, useEffect, useCallback, type ReactNode } from 'react';
import { keycloak, initKeycloak, mapKeycloakToUser } from '../config/keycloak';
import type { User, UserContextType } from '../types/User';

export const UserContext = createContext<UserContextType | undefined>(undefined);

interface UserProviderProps {
  children: ReactNode;
}

export function UserProvider({ children }: UserProviderProps) {
  const [user, setUser] = useState<User | null>(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const init = async () => {
      try {
        const authenticated = await initKeycloak();
        
        if (authenticated) {
          try {
            await keycloak.loadUserProfile();
          } catch (e) {
            console.warn('Could not load user profile');
          }
        }
        
        setIsAuthenticated(authenticated);
        
        if (authenticated) {
          const userData = mapKeycloakToUser(keycloak.instance);
          setUser(userData);
        }
      } catch (error) {
        console.error('Keycloak init error:', error);
      } finally {
        setIsLoading(false);
      }
    };

    init();

    keycloak.onAuthSuccess(async () => {
      await keycloak.loadUserProfile();
      const userData = mapKeycloakToUser(keycloak.instance);
      setUser(userData);
      setIsAuthenticated(true);
    });

    keycloak.onAuthLogout(() => {
      setIsAuthenticated(false);
      setUser(null);
    });

    keycloak.onTokenExpired(() => {
      keycloak.updateToken(30).then(() => {
        const userData = mapKeycloakToUser(keycloak.instance);
        setUser(userData);
        setIsAuthenticated(true);
      }).catch(() => {
        setIsAuthenticated(false);
        setUser(null);
      });
    });
  }, []);

  const login = useCallback(() => {
    keycloak.login();
  }, []);

  const logout = useCallback(() => {
    keycloak.logout();
  }, []);

  return (
    <UserContext.Provider
      value={{
        user,
        isAuthenticated,
        isLoading,
        login,
        logout,
      }}
    >
      {children}
    </UserContext.Provider>
  );
}