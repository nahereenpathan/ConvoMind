import { api } from './client';

export interface ComponentHealthStatus {
  status: 'operational' | 'degraded' | 'down' | 'not_configured';
  provider?: string;
  details: string;
}

export interface AiEngineHealthResponse {
  overall_status: 'operational' | 'degraded' | 'down' | 'not_configured';
  checked_at: string;
  components: {
    whisper: ComponentHealthStatus;
    diarization: ComponentHealthStatus;
    ai_intelligence: ComponentHealthStatus;
    rag: ComponentHealthStatus;
    celery: ComponentHealthStatus;
    redis: ComponentHealthStatus;
    postgresql: ComponentHealthStatus;
  };
}

export const systemApi = {
  getAiEngineHealth: async (forceRefresh = false): Promise<AiEngineHealthResponse> => {
    const res = await api.get<AiEngineHealthResponse>('/system/ai-health', {
      params: forceRefresh ? { refresh: true } : undefined,
    });
    return res.data;
  },
};
