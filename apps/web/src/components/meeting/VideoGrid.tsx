import React from 'react';
import { ParticipantTrackState } from '../../types';
import { ParticipantTile } from './ParticipantTile';
import { Users } from 'lucide-react';

interface VideoGridProps {
  participants: ParticipantTrackState[];
}

export const VideoGrid: React.FC<VideoGridProps> = ({ participants }) => {
  const getGridColsClass = (count: number) => {
    if (count <= 1) return 'grid-cols-1 max-w-3xl mx-auto';
    if (count === 2) return 'grid-cols-1 sm:grid-cols-2';
    if (count <= 4) return 'grid-cols-1 sm:grid-cols-2';
    if (count <= 6) return 'grid-cols-1 sm:grid-cols-2 md:grid-cols-3';
    return 'grid-cols-2 sm:grid-cols-3 md:grid-cols-4';
  };

  if (participants.length === 0) {
    return (
      <div className="min-h-[360px] flex flex-col items-center justify-center space-y-3 bg-[#06152F] border border-[#1D4E78] rounded-2xl p-8 text-center">
        <Users className="w-12 h-12 text-[#8FA4BD]" />
        <h4 className="text-[18px] font-bold text-[#F8FAFC]">Waiting for Participants</h4>
        <p className="text-[14px] text-[#8FA4BD]">Share the meeting link to invite team members.</p>
      </div>
    );
  }

  return (
    <div className={`grid gap-4 w-full h-full min-h-[380px] p-2 ${getGridColsClass(participants.length)}`}>
      {participants.map((p) => (
        <ParticipantTile key={p.id} participant={p} />
      ))}
    </div>
  );
};
