import { api } from './client';
import { IntelligenceResult, IntelligenceJob, ActionItem, ActionItemStatus } from '../types';

export const intelligenceApi = {
  getIntelligence: async (meetingId: string): Promise<IntelligenceResult> => {
    const res = await api.get<IntelligenceResult>(`/meetings/${meetingId}/ai`);
    return res.data;
  },

  generateIntelligence: async (meetingId: string): Promise<IntelligenceJob> => {
    const res = await api.post<IntelligenceJob>(`/meetings/${meetingId}/ai/process`);
    return res.data;
  },

  getIntelligenceStatus: async (meetingId: string, jobId?: string): Promise<IntelligenceJob> => {
    const url = jobId
      ? `/meetings/${meetingId}/ai/status?job_id=${jobId}`
      : `/meetings/${meetingId}/ai/status`;
    const res = await api.get<IntelligenceJob>(url);
    return res.data;
  },

  updateActionItemStatus: async (actionItemId: string, status: ActionItemStatus): Promise<ActionItem> => {
    const res = await api.patch<ActionItem>(`/action-items/${actionItemId}`, { status });
    return res.data;
  },

  updateActionItem: async (actionItemId: string, updates: Partial<ActionItem>): Promise<ActionItem> => {
    const res = await api.patch<ActionItem>(`/action-items/${actionItemId}`, updates);
    return res.data;
  },

  createActionItem: async (meetingId: string, itemData: Partial<ActionItem>): Promise<ActionItem> => {
    const res = await api.post<ActionItem>(`/action-items?meeting_id=${meetingId}`, itemData);
    return res.data;
  },

  deleteActionItem: async (actionItemId: string): Promise<void> => {
    await api.delete(`/action-items/${actionItemId}`);
  },

  getActionItems: async (params: {
    workspace_id: string;
    search?: string;
    status?: string;
    assignee_name?: string;
    assignee_id?: string;
    priority?: string;
    meeting_id?: string;
    due_date_filter?: string;
    page?: number;
    page_size?: number;
    sort_by?: string;
    sort_order?: string;
  }): Promise<{ items: ActionItem[]; total: number; page: number; page_size: number; total_pages: number }> => {
    const query = new URLSearchParams();
    query.set('workspace_id', params.workspace_id);
    if (params.search) query.set('search', params.search);
    if (params.status && params.status !== 'ALL') query.set('status', params.status);
    if (params.assignee_name && params.assignee_name !== 'ALL') query.set('assignee_name', params.assignee_name);
    if (params.assignee_id) query.set('assignee_id', params.assignee_id);
    if (params.priority && params.priority !== 'ALL') query.set('priority', params.priority);
    if (params.meeting_id && params.meeting_id !== 'ALL') query.set('meeting_id', params.meeting_id);
    if (params.due_date_filter && params.due_date_filter !== 'ALL') query.set('due_date_filter', params.due_date_filter);
    if (params.page) query.set('page', params.page.toString());
    if (params.page_size) query.set('page_size', params.page_size.toString());
    if (params.sort_by) query.set('sort_by', params.sort_by);
    if (params.sort_order) query.set('sort_order', params.sort_order);

    const res = await api.get<{ items: ActionItem[]; total: number; page: number; page_size: number; total_pages: number }>(
      `/action-items?${query.toString()}`
    );
    return res.data;
  },

  getActionItemMetrics: async (
    workspaceId: string
  ): Promise<{ total: number; my_tasks: number; overdue: number; completed: number }> => {
    const res = await api.get<{ total: number; my_tasks: number; overdue: number; completed: number }>(
      `/action-items/metrics?workspace_id=${workspaceId}`
    );
    return res.data;
  },
};
