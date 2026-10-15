import React from 'react';
import { X, Sparkles, RefreshCw, CheckCircle2, AlertTriangle, XCircle, HelpCircle } from 'lucide-react';
import { AiEngineHealthResponse, ComponentHealthStatus } from '../../api/system';
import { Button } from '../ui/Button';

interface AiEngineStatusModalProps {
  isOpen: boolean;
  onClose: () => void;
  health: AiEngineHealthResponse | null;
  loading: boolean;
  error: string | null;
  onRefresh: () => void;
}

export const AiEngineStatusModal: React.FC<AiEngineStatusModalProps> = ({
  isOpen,
  onClose,
  health,
  loading,
  error,
  onRefresh,
}) => {
  if (!isOpen) return null;

  const renderStatusBadge = (statusStr: string) => {
    switch (statusStr) {
      case 'operational':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[12px] font-bold bg-[#22C55E]/15 text-[#22C55E] border border-[#22C55E]/40">
            <CheckCircle2 className="w-3.5 h-3.5 mr-1" />
            Operational
          </span>
        );
      case 'degraded':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[12px] font-bold bg-[#F59E0B]/15 text-[#F59E0B] border border-[#F59E0B]/40">
            <AlertTriangle className="w-3.5 h-3.5 mr-1" />
            Degraded
          </span>
        );
      case 'down':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[12px] font-bold bg-[#EF4444]/15 text-[#EF4444] border border-[#EF4444]/40">
            <XCircle className="w-3.5 h-3.5 mr-1" />
            Down
          </span>
        );
      case 'not_configured':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[12px] font-bold bg-[#8FA4BD]/15 text-[#8FA4BD] border border-[#8FA4BD]/40">
            <HelpCircle className="w-3.5 h-3.5 mr-1" />
            Not Configured
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[12px] font-bold bg-[#8FA4BD]/15 text-[#8FA4BD] border border-[#8FA4BD]/40">
            Unavailable
          </span>
        );
    }
  };

  const componentLabels: Record<string, { name: string; desc: string }> = {
    whisper: { name: 'Whisper / STT', desc: 'Audio Speech-to-Text Transcription' },
    diarization: { name: 'Speaker Diarization', desc: 'Multi-Speaker Identification & Segmentation' },
    ai_intelligence: { name: 'AI Intelligence', desc: 'Executive Summary, Key Actions & Decision Extraction' },
    rag: { name: 'RAG & Vector Search', desc: 'Semantic Transcript Search & Grounded QA' },
    celery: { name: 'Celery Worker', desc: 'Asynchronous Meeting Processing Task Pipeline' },
    redis: { name: 'Redis Broker', desc: 'Message Queue & System Cache Store' },
    postgresql: { name: 'PostgreSQL Database', desc: 'Relational Data & Metadata Storage' },
  };

  const getRelativeTime = (isoString?: string) => {
    if (!isoString) return 'Just now';
    const date = new Date(isoString);
    const seconds = Math.floor((new Date().getTime() - date.getTime()) / 1000);
    if (seconds < 5) return 'Just now';
    if (seconds < 60) return `${seconds} seconds ago`;
    const minutes = Math.floor(seconds / 60);
    return `${minutes} minute${minutes > 1 ? 's' : ''} ago`;
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-fade-in">
      <div className="w-full max-w-xl bg-[#102C4D] border border-[#1D4E78] rounded-2xl shadow-2xl overflow-hidden flex flex-col text-[#F8FAFC]">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-[#1D4E78] bg-[#123456]/80">
          <div className="flex items-center space-x-3">
            <div className="p-2.5 rounded-xl bg-[#3B82F6]/20 border border-[#3B82F6]/40 text-[#3B82F6]">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-[18px] font-bold text-[#F8FAFC]">AI Engine Infrastructure Status</h2>
              <p className="text-[12px] text-[#8FA4BD]">Real-time operational readiness of AI pipeline components</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-[#8FA4BD] hover:text-[#F8FAFC] hover:bg-[#1D4E78]/50 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content Body */}
        <div className="p-5 space-y-5 max-h-[70vh] overflow-y-auto">
          {/* Overall Health Card */}
          <div className="p-4 rounded-xl bg-[#123456] border border-[#1D4E78] flex items-center justify-between">
            <div className="space-y-0.5">
              <div className="text-[12px] font-semibold text-[#8FA4BD] uppercase tracking-wider">Overall Status</div>
              <div className="text-[16px] font-bold text-[#F8FAFC]">
                {health?.overall_status === 'operational'
                  ? 'All Core AI Systems Operational'
                  : health?.overall_status === 'degraded'
                  ? 'AI Engine Operating in Degraded Mode'
                  : health?.overall_status === 'down'
                  ? 'Critical AI Infrastructure Offline'
                  : health?.overall_status === 'not_configured'
                  ? 'AI Infrastructure Not Fully Configured'
                  : 'Status Unavailable'}
              </div>
            </div>
            <div>{renderStatusBadge(health?.overall_status || 'unavailable')}</div>
          </div>

          {/* Error Message if API unreachable */}
          {error && (
            <div className="p-4 rounded-xl bg-[#EF4444]/15 border border-[#EF4444]/40 text-[#EF4444] text-[13px] font-semibold flex items-center space-x-2">
              <AlertTriangle className="w-5 h-5 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* Components Grid */}
          <div className="space-y-3">
            <div className="text-[12px] font-bold text-[#8FA4BD] uppercase tracking-wider px-1">
              Component-Level Telemetry
            </div>

            {health?.components ? (
              Object.entries(componentLabels).map(([key, label]) => {
                const comp = health.components[key as keyof typeof health.components] as ComponentHealthStatus | undefined;
                return (
                  <div
                    key={key}
                    className="p-3.5 rounded-xl bg-[#123456]/60 border border-[#1D4E78] hover:border-[#3B82F6]/50 transition-colors flex items-center justify-between gap-3"
                  >
                    <div className="space-y-0.5 min-w-0">
                      <div className="flex items-center space-x-2">
                        <span className="text-[14px] font-semibold text-[#F8FAFC]">{label.name}</span>
                        {comp?.provider && (
                          <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-[#1D4E78] text-[#3B82F6]">
                            {comp.provider}
                          </span>
                        )}
                      </div>
                      <p className="text-[12px] text-[#8FA4BD] truncate">
                        {comp?.details || label.desc}
                      </p>
                    </div>
                    <div className="shrink-0">{renderStatusBadge(comp?.status || 'unavailable')}</div>
                  </div>
                );
              })
            ) : (
              <div className="py-8 text-center text-[#8FA4BD] text-[14px]">
                {loading ? 'Probing AI infrastructure health...' : 'No telemetry data available.'}
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between p-4 border-t border-[#1D4E78] bg-[#123456]/40 text-[12px] text-[#8FA4BD]">
          <div>
            <span>Checked: </span>
            <span className="font-semibold text-[#B8C7DA]">
              {getRelativeTime(health?.checked_at)}
            </span>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={onRefresh}
            isLoading={loading}
            icon={<RefreshCw className={`w-3.5 h-3.5 text-[#3B82F6] ${loading ? 'animate-spin' : ''}`} />}
          >
            Refresh
          </Button>
        </div>
      </div>
    </div>
  );
};
