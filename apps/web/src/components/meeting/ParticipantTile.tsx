import React, { useEffect, useRef } from 'react';
import { MicOff, Volume2, Hand } from 'lucide-react';
import { ParticipantTrackState } from '../../types';

interface ParticipantTileProps {
  participant: ParticipantTrackState;
}

export const ParticipantTile: React.FC<ParticipantTileProps> = ({ participant }) => {
  const videoElementRef = useRef<HTMLVideoElement | null>(null);
  const audioElementRef = useRef<HTMLAudioElement | null>(null);

  const setVideoRef = React.useCallback(
    (node: HTMLVideoElement | null) => {
      videoElementRef.current = node;
      if (node) {
        if (participant.videoTrack && participant.isVideoEnabled) {
          const stream = new MediaStream([participant.videoTrack]);
          node.srcObject = stream;
          node.play().catch((e) => {
            if (e.name !== 'AbortError') {
              console.warn('[ParticipantTile] Video play error:', e);
            }
          });
        } else {
          node.srcObject = null;
        }
      }
    },
    [participant.videoTrack, participant.isVideoEnabled]
  );

  const setAudioRef = React.useCallback(
    (node: HTMLAudioElement | null) => {
      audioElementRef.current = node;
      if (node && !participant.isLocal) {
        if (participant.audioTrack) {
          const stream = new MediaStream([participant.audioTrack]);
          node.srcObject = stream;
          node.play().catch((e) => console.warn('[ParticipantTile] Audio play blocked:', e));
        } else {
          node.srcObject = null;
        }
      }
    },
    [participant.audioTrack, participant.isLocal]
  );

  useEffect(() => {
    if (videoElementRef.current) {
      if (participant.videoTrack && participant.isVideoEnabled) {
        videoElementRef.current.srcObject = new MediaStream([participant.videoTrack]);
        videoElementRef.current.play().catch((e) => {
          if (e.name !== 'AbortError') {
            console.warn('[ParticipantTile] Video play error:', e);
          }
        });
      } else {
        videoElementRef.current.srcObject = null;
      }
    }
  }, [participant.videoTrack, participant.isVideoEnabled]);

  useEffect(() => {
    if (audioElementRef.current && !participant.isLocal) {
      if (participant.audioTrack) {
        audioElementRef.current.srcObject = new MediaStream([participant.audioTrack]);
        audioElementRef.current.play().catch(() => {});
      } else {
        audioElementRef.current.srcObject = null;
      }
    }
  }, [participant.audioTrack, participant.isLocal]);

  return (
    <div
      className={`relative bg-[#102C4D] rounded-2xl overflow-hidden border-2 transition-all duration-300 min-h-[220px] flex flex-col items-center justify-center shadow-xl ${
        participant.isSpeaking
          ? 'border-[#22C55E] ring-4 ring-[#22C55E]/40 shadow-[#22C55E]/20'
          : participant.isLocal
          ? 'border-[#1D4E78]'
          : 'border-[#1D4E78]'
      }`}
    >
      {/* Remote Audio Track Element */}
      {!participant.isLocal && <audio ref={setAudioRef} autoPlay playsInline />}

      {/* Video Track Element or Avatar Fallback */}
      {participant.isVideoEnabled && participant.videoTrack ? (
        <video
          ref={setVideoRef}
          autoPlay
          playsInline
          muted={participant.isLocal}
          className={`w-full h-full object-cover ${participant.isLocal ? 'transform -scale-x-100' : ''}`}
        />
      ) : (
        <div className="flex flex-col items-center justify-center space-y-3 p-6">
          <div className="w-20 h-20 rounded-full bg-[#2563EB] border-2 border-[#3B82F6] flex items-center justify-center text-3xl font-bold text-[#F8FAFC] shadow-lg">
            {(participant.name || 'P').charAt(0).toUpperCase()}
          </div>
          <p className="text-[14px] font-semibold text-[#8FA4BD]">
            {participant.isLocal ? 'Your Camera is Off' : 'Camera Off'}
          </p>
        </div>
      )}

      {/* Hand Raised Badge (Top Left) */}
      {participant.isHandRaised && (
        <div className="absolute top-3 left-3 bg-[#F59E0B] text-white text-[12px] font-bold px-2.5 py-1 rounded-full flex items-center space-x-1.5 shadow-lg animate-bounce">
          <Hand className="w-4 h-4" />
          <span>Hand Raised</span>
        </div>
      )}

      {/* Active Reaction Overlay */}
      {participant.reaction && (
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none bg-black/20 backdrop-blur-[2px] animate-fade-in">
          <span className="text-[64px] drop-shadow-2xl animate-pulse">{participant.reaction}</span>
        </div>
      )}

      {/* Top Right Active Speaker Indicator */}
      {participant.isSpeaking && (
        <div className="absolute top-3 right-3 bg-[#22C55E] text-white text-[11px] font-bold uppercase tracking-wider px-2.5 py-1 rounded-full flex items-center space-x-1 shadow-md animate-pulse">
          <Volume2 className="w-3.5 h-3.5" />
          <span>ACTIVE SPEAKER</span>
        </div>
      )}

      {/* Bottom Name & Audio Status Overlay */}
      <div className="absolute bottom-3 left-3 right-3 flex items-center justify-between bg-[#06152F]/85 backdrop-blur-md px-3 py-1.5 rounded-xl border border-[#1D4E78] text-[13px] text-[#F8FAFC]">
        <div className="flex items-center space-x-2 truncate">
          <span className="font-bold truncate">{participant.name}</span>
          {participant.isLocal && (
            <span className="text-[11px] bg-[#3B82F6]/20 text-[#3B82F6] font-semibold px-2 py-0.5 rounded-full border border-[#3B82F6]/40 shrink-0">
              You
            </span>
          )}
          {participant.role === 'host' && (
            <span className="text-[11px] bg-[#22C55E]/20 text-[#22C55E] font-semibold px-2 py-0.5 rounded-full border border-[#22C55E]/40 shrink-0">
              Host
            </span>
          )}
        </div>

        <div className="shrink-0 ml-2">
          {!participant.isAudioEnabled && (
            <div className="bg-[#EF4444]/20 p-1 rounded-md text-[#EF4444]" title="Microphone Muted">
              <MicOff className="w-3.5 h-3.5" />
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
