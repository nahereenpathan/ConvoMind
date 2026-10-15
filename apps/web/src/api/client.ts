import axios from 'axios';

const envApiUrl = import.meta.env.VITE_API_BASE_URL;
export const API_BASE_URL = envApiUrl
  ? (envApiUrl.endsWith('/api/v1') ? envApiUrl : `${envApiUrl.replace(/\/$/, '')}/api/v1`)
  : '/api/v1';

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('convomind_access_token');
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

let isRefreshing = false;
let failedQueue: Array<{ resolve: (token: string) => void; reject: (err: any) => void }> = [];

const processQueue = (error: any, token: string | null = null) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error);
    } else if (token) {
      prom.resolve(token);
    }
  });
  failedQueue = [];
};

const clearAuthAndRedirect = () => {
  localStorage.removeItem('convomind_user');
  localStorage.removeItem('convomind_access_token');
  localStorage.removeItem('convomind_refresh_token');
  localStorage.removeItem('convomind_active_workspace');
  if (window.location.pathname !== '/login' && window.location.pathname !== '/register') {
    window.location.href = '/login';
  }
};

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    if (error.response?.status === 401 && !originalRequest._retry) {
      if (
        originalRequest.url?.includes('/auth/login') ||
        originalRequest.url?.includes('/auth/register') ||
        originalRequest.url?.includes('/auth/refresh')
      ) {
        return Promise.reject(error);
      }

      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        })
          .then((token) => {
            originalRequest.headers.Authorization = `Bearer ${token}`;
            return api(originalRequest);
          })
          .catch((err) => Promise.reject(err));
      }

      originalRequest._retry = true;
      isRefreshing = true;

      const refreshToken = localStorage.getItem('convomind_refresh_token');

      if (!refreshToken) {
        clearAuthAndRedirect();
        return Promise.reject(error);
      }

      try {
        const response = await axios.post(`${API_BASE_URL}/auth/refresh`, {
          refresh_token: refreshToken,
        });

        const { access_token, refresh_token: newRefreshToken } = response.data;
        localStorage.setItem('convomind_access_token', access_token);
        if (newRefreshToken) {
          localStorage.setItem('convomind_refresh_token', newRefreshToken);
        }

        processQueue(null, access_token);

        originalRequest.headers.Authorization = `Bearer ${access_token}`;
        return api(originalRequest);
      } catch (refreshErr) {
        processQueue(refreshErr, null);
        clearAuthAndRedirect();
        return Promise.reject(refreshErr);
      } finally {
        isRefreshing = false;
      }
    }

    const method = (originalRequest?.method || 'GET').toUpperCase();
    const url = originalRequest?.url || 'unknown';
    const status = error.response?.status;
    const detail = error.response?.data?.detail;
    if (status) {
      console.warn(`[API Error] ${method} ${url} failed with HTTP ${status}:`, detail || error.message);
    } else {
      console.warn(`[API Error] ${method} ${url} failed (network unreachable):`, error.message);
    }

    return Promise.reject(error);
  }
);
