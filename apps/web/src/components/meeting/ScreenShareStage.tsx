import React, { useEffect, useRef } from 'react';
import { Monitor, StopCircle } from 'lucide-react';
import { Button } from '../ui/Button';

interface ScreenShareStageProps {
  sharerName: string;
  isLocalSharer: boolean;
  screenTrack: MediaStreamTrack | null;
  onStopSharing: () => void;
}

export const ScreenShareStage: React.FC<ScreenShareStageProps> = ({
  sharerName,
  isLocalSharer,
  screenTrack,
  onStopSharing,
}) => {
  const videoElementRef = useRef<HTMLVideoElement | null>(null);

  const setVideoRef = React.useCallback(
    (node: HTMLVideoElement | null) => {
      videoElementRef.current = node;
      if (node) {
        if (screenTrack) {
          node.srcObject = new MediaStream([screenTrack]);
        } else {
          node.srcObject = null;
        }
      }
    },
    [screenTrack]
  );

  useEffect(() => {
    if (videoElementRef.current) {
      if (screenTrack) {
        videoElementRef.current.srcObject = new MediaStream([screenTrack]);
      } else {
        videoElementRef.current.srcObject = null;
      }
    }
  }, [screenTrack]);

  return (
    <div className="relative bg-[#06152F] rounded-2xl overflow-hidden border-2 border-[#3B82F6] flex flex-col justify-between shadow-2xl min-h-[420px] w-full">
      {/* Top Banner Header */}
      <div className="absolute top-3 left-3 right-3 z-10 flex items-center justify-between bg-[#06152F]/90 backdrop-blur-md px-4 py-2.5 rounded-xl border border-[#1D4E78] text-[14px]">
        <div className="flex items-center space-x-2.5 text-[#F8FAFC]">
          <Monitor className="w-5 h-5 text-[#3B82F6] animate-pulse" />
          <span className="font-bold">
            {isLocalSharer ? 'You are sharing your screen' : `${sharerName} is sharing screen`}
          </span>
        </div>

        {isLocalSharer && (
          <Button
            variant="danger"
            size="sm"
            onClick={onStopSharing}
            icon={<StopCircle className="w-4 h-4" />}
          >
            Stop Sharing
          </Button>
        )}
      </div>

      {/* Main Video Stream Rendering */}
      {screenTrack ? (
        <video
          ref={setVideoRef}
          autoPlay
          playsInline
          muted={isLocalSharer}
          className="w-full h-full object-contain bg-[#020B19]"
        />
      ) : (
        <div className="flex flex-col items-center justify-center my-auto p-12 text-[#8FA4BD] space-y-3">
          <Monitor className="w-16 h-16 text-[#3B82F6] animate-pulse" />
          <p className="text-[16px] font-semibold text-[#F8FAFC]">Connecting screen stream...</p>
        </div>
      )}
    </div>
  );
};
