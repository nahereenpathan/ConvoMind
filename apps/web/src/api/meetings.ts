import { api } from './client';
import { Meeting, MeetingStatus, Recording } from '../types';

export interface MeetingFilters {
  workspace_id?: string;
  status?: MeetingStatus;
  search?: string;
}

export const meetingsApi = {
  getMeetings: async (filters?: MeetingFilters): Promise<Meeting[]> => {
    const res = await api.get<any>('/meetings', { params: filters });
    if (res.data && 'items' in res.data && Array.isArray(res.data.items)) {
      return res.data.items;
    }
    return Array.isArray(res.data) ? res.data : [];
  },

  getMeeting: async (id: string): Promise<Meeting> => {
    const res = await api.get<Meeting>(`/meetings/${id}`);
    return res.data;
  },

  createMeeting: async (data: {
    title: string;
    description?: string;
    workspace_id: string;
    scheduled_at?: string;
  }): Promise<Meeting> => {
    const res = await api.post<Meeting>('/meetings', data);
    return res.data;
  },

  updateMeeting: async (id: string, data: Partial<Meeting>): Promise<Meeting> => {
    const res = await api.patch<Meeting>(`/meetings/${id}`, data);
    return res.data;
  },

  deleteMeeting: async (id: string): Promise<void> => {
    await api.delete(`/meetings/${id}`);
  },

  moveToTrash: async (id: string): Promise<void> => {
    await api.delete(`/meetings/${id}`);
  },

  getTrashMeetings: async (filters?: MeetingFilters): Promise<Meeting[]> => {
    const res = await api.get<any>('/meetings/trash', { params: filters });
    if (res.data && 'items' in res.data && Array.isArray(res.data.items)) {
      return res.data.items;
    }
    return Array.isArray(res.data) ? res.data : [];
  },

  restoreMeeting: async (id: string): Promise<void> => {
    await api.post(`/meetings/${id}/restore`);
  },

  permanentlyDeleteMeeting: async (id: string): Promise<void> => {
    await api.delete(`/meetings/${id}/permanent`);
  },

  uploadRecording: async (
    meetingId: string,
    file: File,
    onProgress?: (progress: number) => void
  ): Promise<Recording> => {
    const formData = new FormData();
    formData.append('file', file);

    const res = await api.post<Recording>(`/meetings/${meetingId}/recordings`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      onUploadProgress: (progressEvent) => {
        if (progressEvent.total && onProgress) {
          const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          onProgress(percentCompleted);
        }
      },
    });
    return res.data;
  },

  getRecordings: async (meetingId: string): Promise<Recording[]> => {
    const res = await api.get<any>(`/meetings/${meetingId}/recordings`);
    if (res.data && 'items' in res.data && Array.isArray(res.data.items)) {
      return res.data.items;
    }
    return Array.isArray(res.data) ? res.data : [];
  },

  transcribeRecording: async (meetingId: string, recordingId: string): Promise<any> => {
    const res = await api.post(`/meetings/${meetingId}/recordings/${recordingId}/transcribe`);
    return res.data;
  },

  processMeeting: async (meetingId: string, recordingId?: string): Promise<any> => {
    let targetRecordingId = recordingId;

    if (!targetRecordingId) {
      const recordings = await meetingsApi.getRecordings(meetingId);
      if (recordings.length > 0) {
        targetRecordingId = recordings[0].id;
      }
    }

    if (!targetRecordingId) {
      throw new Error('No recording file found for this meeting to process.');
    }

    return meetingsApi.transcribeRecording(meetingId, targetRecordingId);
  },

  initNativeRoom: async (meetingId: string): Promise<any> => {
    const res = await api.post(`/meetings/${meetingId}/native-room`);
    return res.data;
  },

  joinNativeRoom: async (meetingId: string): Promise<{
    meeting_id: string;
    room_id: string;
    ws_url: string;
    token: string;
    is_host: boolean;
    participant_identity: string;
    participant_name: string;
    room_status: string;
  }> => {
    const res = await api.post(`/meetings/${meetingId}/join`);
    return res.data;
  },

  leaveNativeRoom: async (meetingId: string): Promise<void> => {
    await api.post(`/meetings/${meetingId}/leave`);
  },

  endNativeRoom: async (meetingId: string): Promise<Meeting> => {
    const res = await api.post<Meeting>(`/meetings/${meetingId}/end`);
    return res.data;
  },

  getNativeRoomStatus: async (meetingId: string): Promise<any> => {
    const res = await api.get(`/meetings/${meetingId}/room`);
    return res.data;
  },

  sendMeetingMessage: async (meetingId: string, message: string): Promise<any> => {
    const res = await api.post(`/meetings/${meetingId}/messages`, { message });
    return res.data;
  },

  getMeetingMessages: async (meetingId: string): Promise<any[]> => {
    const res = await api.get(`/meetings/${meetingId}/messages`);
    return Array.isArray(res.data) ? res.data : [];
  },

  startNativeRecording: async (meetingId: string): Promise<any> => {
    const res = await api.post(`/meetings/${meetingId}/recording/start`);
    return res.data;
  },

  stopNativeRecording: async (meetingId: string): Promise<any> => {
    const res = await api.post(`/meetings/${meetingId}/recording/stop`);
    return res.data;
  },

  muteParticipant: async (meetingId: string, participantId: string): Promise<any> => {
    const res = await api.post(`/meetings/${meetingId}/participants/${participantId}/mute`);
    return res.data;
  },

  kickParticipant: async (meetingId: string, participantId: string): Promise<any> => {
    const res = await api.post(`/meetings/${meetingId}/participants/${participantId}/kick`);
    return res.data;
  },
};


