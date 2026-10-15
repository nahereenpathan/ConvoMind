import { api } from './client';
import { AppNotification } from '../types';

export const notificationsApi = {
  getNotifications: async (unreadOnly = false): Promise<AppNotification[]> => {
    const res = await api.get<any>('/notifications', {
      params: { unread_only: unreadOnly },
    });
    if (res.data && 'items' in res.data && Array.isArray(res.data.items)) {
      return res.data.items;
    }
    return Array.isArray(res.data) ? res.data : [];
  },

  markAsRead: async (id: string): Promise<AppNotification> => {
    const res = await api.patch<AppNotification>(`/notifications/${id}/read`);
    return res.data;
  },

  markAsUnread: async (id: string): Promise<AppNotification> => {
    const res = await api.patch<AppNotification>(`/notifications/${id}/unread`);
    return res.data;
  },

  markAllAsRead: async (): Promise<void> => {
    await api.patch('/notifications/read-all');
  },

  deleteNotification: async (id: string): Promise<void> => {
    await api.delete(`/notifications/${id}`);
  },

  clearAllNotifications: async (): Promise<void> => {
    await api.delete('/notifications');
  },

  testSmtpConnection: async (targetEmail?: string): Promise<{ message: string }> => {
    const res = await api.post<{ message: string }>('/notifications/test-smtp', {
      target_email: targetEmail,
    });
    return res.data;
  },
};

