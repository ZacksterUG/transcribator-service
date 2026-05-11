export interface User {
  id: string;
  email: string;
  name: string;
  roles: string[];
}

export interface UserContextType {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: () => void;
  logout: () => void;
}