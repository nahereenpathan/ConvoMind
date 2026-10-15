import React from 'react';
import { Users, X, Mic, MicOff, Video, VideoOff, Monitor, Hand, UserX, VolumeX } from 'lucide-react';
import { ParticipantTrackState } from '../../types';
import { Button } from '../ui/Button';

interface ParticipantPanelProps {
  participants: ParticipantTrackState[];
  isHost: boolean;
  onClose: () => void;
  onEndRoom?: () => void;
  onMuteParticipant?: (participantId: string) => void;
  onKickParticipant?: (participantId: string) => void;
}

export const ParticipantPanel: React.FC<ParticipantPanelProps> = ({
  participants,
  isHost,
  onClose,
  onEndRoom,
  onMuteParticipant,
  onKickParticipant,
}) => {
  const raisedCount = participants.filter((p) => p.isHandRaised).length;

  return (
    <div className="w-full md:w-80 lg:w-96 bg-[#102C4D] border border-[#1D4E78] rounded-2xl flex flex-col h-[520px] shadow-2xl overflow-hidden text-[#F8FAFC]">
      {/* Header */}
      <div className="p-4 bg-[#06152F] border-b border-[#1D4E78] flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <Users className="w-4 h-4 text-[#3B82F6]" />
          <h3 className="text-[16px] font-bold text-[#F8FAFC]">
            People ({participants.length})
            {raisedCount > 0 && <span className="ml-2 text-[12px] text-[#F59E0B]">✋ {raisedCount} Raised</span>}
          </h3>
        </div>
        <button
          onClick={onClose}
          className="text-[#8FA4BD] hover:text-[#F8FAFC] transition-colors p-1"
          title="Close Panel"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Participant List */}
      <div className="flex-1 p-4 space-y-2.5 overflow-y-auto custom-scrollbar">
        {participants.map((p) => (
          <div
            key={p.id}
            className="flex flex-col p-3 rounded-xl bg-[#06152F]/70 border border-[#1D4E78] text-[13px] space-y-2"
          >
            <div className="flex items-center justify-between">
              {/* Left: Avatar & Name */}
              <div className="flex items-center space-x-3 truncate">
                <div className="w-9 h-9 rounded-full bg-[#2563EB] flex items-center justify-center font-bold text-white shrink-0 shadow-sm relative">
                  {(p.name || 'P').charAt(0).toUpperCase()}
                  {p.isHandRaised && (
                    <span className="absolute -top-1 -right-1 text-xs">✋</span>
                  )}
                </div>
                <div className="truncate">
                  <div className="flex items-center space-x-1.5 truncate">
                    <span className="font-semibold text-[#F8FAFC] truncate">{p.name}</span>
                    {p.isLocal && (
                      <span className="text-[10px] bg-[#3B82F6]/20 text-[#3B82F6] font-semibold px-1.5 py-0.5 rounded border border-[#3B82F6]/40 shrink-0">
                        You
                      </span>
                    )}
                    {p.role === 'host' && (
                      <span className="text-[10px] bg-[#22C55E]/20 text-[#22C55E] font-semibold px-1.5 py-0.5 rounded border border-[#22C55E]/40 shrink-0">
                        Host
                      </span>
                    )}
                  </div>
                  <p className="text-[11px] text-[#8FA4BD]">
                    {p.isSpeaking
                      ? 'Speaking...'
                      : p.isHandRaised
                      ? 'Hand Raised'
                      : p.isScreenSharing
                      ? 'Sharing Screen'
                      : 'Connected'}
                  </p>
                </div>
              </div>

              {/* Right: Media Track Indicators */}
              <div className="flex items-center space-x-1.5 shrink-0">
                {p.isHandRaised && (
                  <div className="p-1 rounded bg-[#F59E0B]/20 text-[#F59E0B]" title="Hand Raised">
                    <Hand className="w-4 h-4" />
                  </div>
                )}

                {p.isScreenSharing && (
                  <div className="p-1 rounded bg-[#3B82F6]/20 text-[#3B82F6]" title="Sharing Screen">
                    <Monitor className="w-4 h-4" />
                  </div>
                )}

                {p.isAudioEnabled ? (
                  <div className="p-1 rounded text-[#22C55E]" title="Microphone Active">
                    <Mic className="w-4 h-4" />
                  </div>
                ) : (
                  <div className="p-1 rounded text-[#EF4444]" title="Microphone Muted">
                    <MicOff className="w-4 h-4" />
                  </div>
                )}

                {p.isVideoEnabled ? (
                  <div className="p-1 rounded text-[#3B82F6]" title="Camera Active">
                    <Video className="w-4 h-4" />
                  </div>
                ) : (
                  <div className="p-1 rounded text-[#8FA4BD]" title="Camera Off">
                    <VideoOff className="w-4 h-4" />
                  </div>
                )}
              </div>
            </div>

            {/* Host Moderation Controls for Remote Attendees */}
            {isHost && !p.isLocal && (
              <div className="flex items-center justify-end space-x-2 pt-1 border-t border-[#1D4E78]/50 text-[11px]">
                {onMuteParticipant && p.isAudioEnabled && (
                  <button
                    onClick={() => onMuteParticipant(p.id)}
                    className="px-2 py-1 bg-[#123456] hover:bg-[#1D4E78] text-[#F8FAFC] rounded flex items-center space-x-1 transition-colors"
                  >
                    <VolumeX className="w-3 h-3 text-[#EF4444]" />
                    <span>Mute</span>
                  </button>
                )}
                {onKickParticipant && (
                  <button
                    onClick={() => onKickParticipant(p.id)}
                    className="px-2 py-1 bg-[#EF4444]/15 hover:bg-[#EF4444]/30 text-[#EF4444] rounded flex items-center space-x-1 transition-colors"
                  >
                    <UserX className="w-3 h-3" />
                    <span>Remove</span>
                  </button>
                )}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Host Action Footer */}
      {isHost && onEndRoom && (
        <div className="p-3 bg-[#06152F] border-t border-[#1D4E78]">
          <Button variant="danger" size="sm" onClick={onEndRoom} className="w-full">
            End Meeting for All
          </Button>
        </div>
      )}
    </div>
  );
};
