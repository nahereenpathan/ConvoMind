import { api } from './client';
import { Workspace, WorkspaceMember, UserRole } from '../types';

export const workspaceApi = {
  getWorkspaces: async (): Promise<Workspace[]> => {
    const res = await api.get<Workspace[]>('/workspaces');
    return Array.isArray(res.data) ? res.data : [];
  },

  getWorkspace: async (id: string): Promise<Workspace> => {
    const res = await api.get<Workspace>(`/workspaces/${id}`);
    return res.data;
  },

  createWorkspace: async (data: { name: string; description?: string }): Promise<Workspace> => {
    const res = await api.post<Workspace>('/workspaces', data);
    return res.data;
  },

  updateWorkspace: async (id: string, data: { name?: string; description?: string }): Promise<Workspace> => {
    const res = await api.patch<Workspace>(`/workspaces/${id}`, data);
    return res.data;
  },

  getMembers: async (workspaceId: string): Promise<WorkspaceMember[]> => {
    const res = await api.get<WorkspaceMember[]>(`/workspaces/${workspaceId}/members`);
    return Array.isArray(res.data) ? res.data : [];
  },

  addMember: async (workspaceId: string, email: string, role: UserRole = UserRole.MEMBER): Promise<WorkspaceMember> => {
    const res = await api.post<WorkspaceMember>(`/workspaces/${workspaceId}/members`, { email, role });
    return res.data;
  },

  updateMemberRole: async (workspaceId: string, userId: string, role: UserRole): Promise<WorkspaceMember> => {
    const res = await api.patch<WorkspaceMember>(`/workspaces/${workspaceId}/members/${userId}`, { role });
    return res.data;
  },

  removeMember: async (workspaceId: string, userId: string): Promise<void> => {
    await api.delete(`/workspaces/${workspaceId}/members/${userId}`);
  },
};
