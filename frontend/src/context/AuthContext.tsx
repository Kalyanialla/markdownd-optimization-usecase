import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import type { User, LoginPayload, SignupPayload, TokenResponse } from '../types/auth';
import { apiClient, setAccessToken } from '../lib/api';

interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (payload: LoginPayload) => Promise<void>;
  signup: (payload: SignupPayload) => Promise<void>;
  logout: () => Promise<void>;
  refreshProfile: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const fetchProfile = useCallback(async () => {
    try {
      const currentUser = await apiClient<User>('/auth/me');
      setUser(currentUser);
    } catch {
      setUser(null);
      setAccessToken(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchProfile();

    const handleSessionExpired = () => {
      setUser(null);
      setAccessToken(null);
    };

    window.addEventListener('auth:session-expired', handleSessionExpired);
    return () => {
      window.removeEventListener('auth:session-expired', handleSessionExpired);
    };
  }, [fetchProfile]);

  const login = async (payload: LoginPayload) => {
    const res = await apiClient<TokenResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    setAccessToken(res.access_token);
    setUser(res.user);
  };

  const signup = async (payload: SignupPayload) => {
    const res = await apiClient<TokenResponse>('/auth/signup', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    setAccessToken(res.access_token);
    setUser(res.user);
  };

  const logout = async () => {
    try {
      await apiClient('/auth/logout', {
        method: 'POST',
        body: JSON.stringify({}),
      });
    } catch (err) {
      console.warn('Logout request warning:', err);
    } finally {
      setAccessToken(null);
      setUser(null);
    }
  };

  const refreshProfile = async () => {
    await fetchProfile();
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isLoading,
        isAuthenticated: !!user,
        login,
        signup,
        logout,
        refreshProfile,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
