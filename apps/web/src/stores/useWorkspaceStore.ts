import { create } from 'zustand';
import { Workspace } from '../types';
import { workspaceApi } from '../api/workspace';
import { useAuthStore } from './useAuthStore';

const safeJSONParse = <T>(key: string, fallback: T): T => {
  try {
    const val = localStorage.getItem(key);
    if (!val || val === 'undefined' || val === 'null') return fallback;
    return JSON.parse(val);
  } catch {
    return fallback;
  }
};

interface WorkspaceState {
  activeWorkspace: Workspace | null;
  workspaces: Workspace[];
  isLoading: boolean;
  setActiveWorkspace: (workspace: Workspace | null) => void;
  setWorkspaces: (workspaces: Workspace[]) => void;
  fetchWorkspaces: () => Promise<void>;
  createWorkspace: (name: string, description?: string) => Promise<Workspace>;
  updateWorkspace: (id: string, name: string, description?: string) => Promise<Workspace>;
}

export const useWorkspaceStore = create<WorkspaceState>((set, get) => ({
  activeWorkspace: safeJSONParse<Workspace | null>('convomind_active_workspace', null),
  workspaces: [],
  isLoading: false,

  setActiveWorkspace: (workspace: Workspace | null) => {
    if (workspace) {
      localStorage.setItem('convomind_active_workspace', JSON.stringify(workspace));
    } else {
      localStorage.removeItem('convomind_active_workspace');
    }
    set({ activeWorkspace: workspace });
  },

  setWorkspaces: (workspaces: Workspace[]) => {
    const current = get().activeWorkspace;
    let nextActive = current;

    if (!current && workspaces.length > 0) {
      nextActive = workspaces[0];
      localStorage.setItem('convomind_active_workspace', JSON.stringify(nextActive));
    } else if (current) {
      const matched = workspaces.find((w) => w.id === current.id);
      if (matched) nextActive = matched;
    }

    set({ workspaces, activeWorkspace: nextActive });
  },

  fetchWorkspaces: async () => {
    set({ isLoading: true });
    try {
      const list = await workspaceApi.getWorkspaces();
      if (list.length === 0) {
        const user = useAuthStore.getState().user;
        const defaultName = user?.full_name ? `${user.full_name}'s Workspace` : 'My Workspace';
        try {
          const created = await workspaceApi.createWorkspace({ name: defaultName });
          get().setWorkspaces([created]);
          get().setActiveWorkspace(created);
          return;
        } catch (err) {
          console.error('Failed to auto-create default workspace', err);
        }
      }
      get().setWorkspaces(list);
    } catch (e) {
      console.error('Failed to fetch workspaces', e);
    } finally {
      set({ isLoading: false });
    }
  },

  createWorkspace: async (name: string, description?: string) => {
    set({ isLoading: true });
    try {
      const created = await workspaceApi.createWorkspace({ name, description });
      await get().fetchWorkspaces();
      get().setActiveWorkspace(created);
      return created;
    } finally {
      set({ isLoading: false });
    }
  },

  updateWorkspace: async (id: string, name: string, description?: string) => {
    set({ isLoading: true });
    try {
      const updated = await workspaceApi.updateWorkspace(id, { name, description });
      await get().fetchWorkspaces();
      if (get().activeWorkspace?.id === id) {
        get().setActiveWorkspace(updated);
      }
      return updated;
    } finally {
      set({ isLoading: false });
    }
  },
}));
