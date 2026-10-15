import { api } from './client';
import { FollowUpEmail } from '../types';

interface BackendFollowUp {
  id: string;
  workspace_id?: string;
  meeting_id: string;
  type?: string;
  status: any;
  subject: string;
  content?: string;
  body?: string;
  recipients?: string[];
  created_at?: string;
  updated_at?: string;
}

const mapFollowUp = (raw: BackendFollowUp): FollowUpEmail => ({
  id: raw.id,
  workspace_id: raw.workspace_id,
  meeting_id: raw.meeting_id,
  type: raw.type as any,
  status: raw.status,
  subject: raw.subject,
  body: raw.content || raw.body || '',
  recipients: raw.recipients || [],
  created_at: raw.created_at,
  updated_at: raw.updated_at,
});

export const followUpsApi = {
  getFollowUps: async (meetingId: string): Promise<FollowUpEmail[]> => {
    const res = await api.get<BackendFollowUp[]>(`/meetings/${meetingId}/follow-ups`);
    const list = Array.isArray(res.data) ? res.data : [];
    return list.map(mapFollowUp);
  },

  generateFollowUp: async (meetingId: string, type: string = 'EMAIL_DRAFT'): Promise<FollowUpEmail> => {
    const res = await api.post<BackendFollowUp>(`/meetings/${meetingId}/follow-ups/generate`, { type });
    return mapFollowUp(res.data);
  },

  updateFollowUp: async (
    id: string,
    data: { subject?: string; body?: string; recipients?: string[] }
  ): Promise<FollowUpEmail> => {
    const payload: Record<string, any> = {};
    if (data.subject !== undefined) payload.subject = data.subject;
    if (data.body !== undefined) payload.content = data.body;
    if (data.recipients !== undefined) payload.recipients = data.recipients;

    const res = await api.patch<BackendFollowUp>(`/follow-ups/${id}`, payload);
    return mapFollowUp(res.data);
  },

  sendFollowUp: async (id: string): Promise<FollowUpEmail> => {
    const res = await api.post<BackendFollowUp>(`/follow-ups/${id}/send`);
    return mapFollowUp(res.data);
  },
};

