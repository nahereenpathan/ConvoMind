import { api } from './client';
import { TranscriptSegment } from '../types';

export const transcriptsApi = {
  getTranscript: async (meetingId: string): Promise<TranscriptSegment[]> => {
    const res = await api.get<any>(`/meetings/${meetingId}/transcript`);
    if (res.data && 'segments' in res.data && Array.isArray(res.data.segments)) {
      return res.data.segments;
    }
    return Array.isArray(res.data) ? res.data : [];
  },

  getTranscriptFull: async (meetingId: string): Promise<any> => {
    const res = await api.get<any>(`/meetings/${meetingId}/transcript`);
    return res.data;
  },

  updateSegment: async (
    meetingId: string,
    segmentId: string,
    text: string,
    speakerLabel?: string
  ): Promise<TranscriptSegment> => {
    const res = await api.patch<TranscriptSegment>(
      `/meetings/${meetingId}/transcript/segments/${segmentId}`,
      {
        text,
        speaker_label: speakerLabel,
      }
    );
    return res.data;
  },
};
