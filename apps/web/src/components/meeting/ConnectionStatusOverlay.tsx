import React from 'react';
import { ShieldAlert, ArrowLeft, RefreshCw, CheckCircle2 } from 'lucide-react';
import { Card } from '../ui/Card';
import { Button } from '../ui/Button';
import { MeetingRoomState } from '../../types';

interface ConnectionStatusOverlayProps {
  roomState: MeetingRoomState;
  errorMessage?: string | null;
  onReturnToMeetings: () => void;
  onRetry?: () => void;
}

export const ConnectionStatusOverlay: React.FC<ConnectionStatusOverlayProps> = ({
  roomState,
  errorMessage,
  onReturnToMeetings,
  onRetry,
}) => {
  if (roomState === 'CONNECTING') {
    return (
      <div className="min-h-[60vh] flex flex-col items-center justify-center space-y-4 text-[#F8FAFC]">
        <div className="w-12 h-12 border-4 border-[#3B82F6] border-t-transparent rounded-full animate-spin" />
        <h3 className="text-[18px] font-bold">Connecting to ConvoMind Meeting Room...</h3>
        <p className="text-[14px] text-[#8FA4BD]">Establishing media encryption and WebRTC session connection.</p>
      </div>
    );
  }

  if (roomState === 'RECONNECTING') {
    return (
      <div className="p-4 rounded-xl bg-[#3B82F6]/20 border border-[#3B82F6]/40 flex items-center space-x-3 text-[#F8FAFC] animate-pulse">
        <RefreshCw className="w-5 h-5 text-[#3B82F6] animate-spin shrink-0" />
        <div>
          <p className="text-[14px] font-bold">Connection Interrupted</p>
          <p className="text-[12px] text-[#B8C7DA]">Reconnecting to media server automatically...</p>
        </div>
      </div>
    );
  }

  if (roomState === 'DISCONNECTED') {
    return (
      <div className="max-w-md mx-auto pt-12 space-y-4 text-center text-[#F8FAFC]">
        <Card className="bg-[#102C4D] border border-[#1D4E78] p-8 space-y-4 shadow-2xl">
          <CheckCircle2 className="w-12 h-12 text-[#22C55E] mx-auto" />
          <h3 className="text-[20px] font-bold">You Left the Meeting</h3>
          <p className="text-[14px] text-[#B8C7DA]">Thank you for using ConvoMind Native Meetings.</p>
          <div className="pt-2">
            <Button onClick={onReturnToMeetings} className="w-full">
              Return to Meetings List
            </Button>
          </div>
        </Card>
      </div>
    );
  }

  if (roomState === 'ENDED') {
    return (
      <div className="max-w-md mx-auto pt-12 space-y-4 text-center text-[#F8FAFC]">
        <Card className="bg-[#102C4D] border border-[#1D4E78] p-8 space-y-4 shadow-2xl">
          <CheckCircle2 className="w-12 h-12 text-[#3B82F6] mx-auto" />
          <h3 className="text-[20px] font-bold">Meeting Has Ended</h3>
          <p className="text-[14px] text-[#B8C7DA]">The host has closed this meeting room for all participants.</p>
          <div className="pt-2">
            <Button onClick={onReturnToMeetings} className="w-full">
              Return to Meetings List
            </Button>
          </div>
        </Card>
      </div>
    );
  }

  if (roomState === 'ERROR') {
    return (
      <div className="max-w-lg mx-auto pt-12 space-y-5 text-[#F8FAFC]">
        <button
          onClick={onReturnToMeetings}
          className="flex items-center space-x-2 text-[14px] font-semibold text-[#8FA4BD] hover:text-[#F8FAFC] transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Meetings</span>
        </button>

        <Card className="bg-[#102C4D] border border-[#EF4444]/40 p-6 space-y-4 shadow-2xl">
          <div className="flex items-center space-x-3 text-[#EF4444]">
            <ShieldAlert className="w-6 h-6 shrink-0" />
            <h3 className="text-[18px] font-bold">Unable to Join Real-Time Room</h3>
          </div>
          <p className="text-[14px] text-[#B8C7DA] leading-relaxed">
            {errorMessage || 'Failed to authenticate meeting room credentials or establish media connection.'}
          </p>
          <div className="flex items-center space-x-3 pt-2">
            {onRetry && (
              <Button onClick={onRetry} variant="primary">
                Try Again
              </Button>
            )}
            <Button variant="outline" onClick={onReturnToMeetings}>
              Return to Meetings List
            </Button>
          </div>
        </Card>
      </div>
    );
  }

  return null;
};
