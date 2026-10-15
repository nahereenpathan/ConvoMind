import { api } from './client';
import { ChatResponse, ChatMessage } from '../types';

export const chatApi = {
  sendMessage: async (meetingId: string, query: string): Promise<ChatResponse> => {
    const res = await api.post<any>(`/meetings/${meetingId}/chat`, { question: query });
    const data = res.data;
    const answer = data.assistant_message?.content || data.answer || '';
    const citations = data.sources || data.citations || [];
    return { answer, citations };
  },

  getHistory: async (meetingId: string): Promise<ChatMessage[]> => {
    try {
      const res = await api.get<any>(`/meetings/${meetingId}/chat/history`);
      return Array.isArray(res.data) ? res.data : [];
    } catch {
      return [];
    }
  },
};
