import { api } from './client';
import { SpeakerMap } from '../types';

export const speakersApi = {
  getSpeakers: async (meetingId: string): Promise<SpeakerMap[]> => {
    const res = await api.get<SpeakerMap[]>(`/meetings/${meetingId}/speakers`);
    return Array.isArray(res.data) ? res.data : [];
  },

  runDiarization: async (meetingId: string): Promise<any> => {
    const res = await api.post(`/meetings/${meetingId}/speakers/diarize`);
    return res.data;
  },

  updateSpeakerName: async (meetingId: string, speakerLabel: string, displayName: string, speakerId?: string): Promise<SpeakerMap> => {
    if (speakerId) {
      const res = await api.patch<SpeakerMap>(`/meetings/${meetingId}/speakers/${speakerId}`, {
        speaker_label: speakerLabel,
        display_name: displayName,
      });
      return res.data;
    } else {
      const res = await api.post<SpeakerMap>(`/meetings/${meetingId}/speakers`, {
        speaker_label: speakerLabel,
        display_name: displayName,
      });
      return res.data;
    }
  },
};
