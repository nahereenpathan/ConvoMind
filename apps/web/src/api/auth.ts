import { api } from './client';
import { AuthResponse, User, LoginCredentials, RegisterCredentials } from '../types';

export const authApi = {
  login: async (credentials: LoginCredentials): Promise<AuthResponse> => {
    const res = await api.post<AuthResponse>('/auth/login', credentials);
    return res.data;
  },

  register: async (credentials: RegisterCredentials): Promise<AuthResponse> => {
    const res = await api.post<AuthResponse>('/auth/register', credentials);
    return res.data;
  },

  getCurrentUser: async (): Promise<User> => {
    const res = await api.get<User>('/auth/me');
    return res.data;
  },

  updateProfile: async (data: Partial<User>): Promise<User> => {
    const res = await api.put<User>('/auth/me', data);
    return res.data;
  },

  forgotPassword: async (email: string): Promise<{ message: string }> => {
    const res = await api.post<{ message: string }>('/auth/forgot-password', { email });
    return res.data;
  },

  resetPassword: async (token: string, new_password: string): Promise<{ message: string }> => {
    const res = await api.post<{ message: string }>('/auth/reset-password', { token, new_password });
    return res.data;
  },
};
