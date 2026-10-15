import { create } from 'zustand';
import { User } from '../types';
import { authApi } from '../api/auth';

const safeJSONParse = <T>(key: string, fallback: T): T => {
  try {
    const val = localStorage.getItem(key);
    if (!val || val === 'undefined' || val === 'null') return fallback;
    return JSON.parse(val);
  } catch {
    return fallback;
  }
};

interface AuthState {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  setAuth: (user: User, accessToken: string, refreshToken: string) => void;
  setUser: (user: User) => void;
  setTokens: (accessToken: string, refreshToken: string) => void;
  login: (email: string, pass: string) => Promise<void>;
  register: (email: string, pass: string, name: string) => Promise<void>;
  fetchCurrentUser: () => Promise<void>;
  logout: () => void;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: safeJSONParse<User | null>('convomind_user', null),
  accessToken: localStorage.getItem('convomind_access_token'),
  refreshToken: localStorage.getItem('convomind_refresh_token'),
  isAuthenticated: !!localStorage.getItem('convomind_access_token'),
  isLoading: false,

  setAuth: (user, accessToken, refreshToken) => {
    if (user) {
      localStorage.setItem('convomind_user', JSON.stringify(user));
    } else {
      localStorage.removeItem('convomind_user');
    }
    if (accessToken) {
      localStorage.setItem('convomind_access_token', accessToken);
    }
    if (refreshToken) {
      localStorage.setItem('convomind_refresh_token', refreshToken);
    }
    set({
      user,
      accessToken,
      refreshToken,
      isAuthenticated: !!accessToken,
    });
  },

  setUser: (user) => {
    if (user) {
      localStorage.setItem('convomind_user', JSON.stringify(user));
    } else {
      localStorage.removeItem('convomind_user');
    }
    set({ user });
  },

  setTokens: (accessToken, refreshToken) => {
    if (accessToken) {
      localStorage.setItem('convomind_access_token', accessToken);
    }
    if (refreshToken) {
      localStorage.setItem('convomind_refresh_token', refreshToken);
    }
    set({ accessToken, refreshToken, isAuthenticated: !!accessToken });
  },

  login: async (email, password) => {
    set({ isLoading: true });
    try {
      const res = await authApi.login({ email, password });
      get().setTokens(res.access_token, res.refresh_token);
      await get().fetchCurrentUser();
    } finally {
      set({ isLoading: false });
    }
  },

  register: async (email, password, name) => {
    set({ isLoading: true });
    try {
      await authApi.register({ email, password, name });
      await get().login(email, password);
    } finally {
      set({ isLoading: false });
    }
  },

  fetchCurrentUser: async () => {
    if (!get().accessToken) return;
    try {
      const user = await authApi.getCurrentUser();
      get().setUser(user);
    } catch (e) {
      console.error('Failed to fetch current user', e);
    }
  },

  logout: () => {
    localStorage.removeItem('convomind_user');
    localStorage.removeItem('convomind_access_token');
    localStorage.removeItem('convomind_refresh_token');
    localStorage.removeItem('convomind_active_workspace');
    set({
      user: null,
      accessToken: null,
      refreshToken: null,
      isAuthenticated: false,
    });
  },
}));
