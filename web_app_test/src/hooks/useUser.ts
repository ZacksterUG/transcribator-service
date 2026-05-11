import { useContext } from 'react';
import { UserContext } from '../context/UserContext';
import type { User } from '../types/User';

interface UseUserReturn {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (user: User) => void;
  logout: () => void;
}

export function useUser(): UseUserReturn {
  const context = useContext(UserContext);
  if (context === undefined) {
    throw new Error('useUser must be used within a UserProvider');
  }
  return context;
}