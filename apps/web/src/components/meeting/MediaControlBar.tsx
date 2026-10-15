import React, { useState } from 'react';
import {
  Mic,
  MicOff,
  Video,
  VideoOff,
  Monitor,
  MessageSquare,
  Users,
  PhoneOff,
  StopCircle,
  Radio,
  Hand,
  Smile,
  Settings,
} from 'lucide-react';
import { Button } from '../ui/Button';

interface MediaControlBarProps {
  micOn: boolean;
  cameraOn: boolean;
  isScreenSharing: boolean;
  isRecording: boolean;
  isRecordingLoading?: boolean;
  isHandRaised?: boolean;
  activePanel: 'none' | 'chat' | 'people';
  participantCount: number;
  unreadChatCount?: number;
  isHost: boolean;
  isEnding: boolean;
  onToggleMic: () => void;
  onToggleCamera: () => void;
  onToggleScreenShare: () => void;
  onToggleRecording: () => void;
  onToggleHandRaise?: () => void;
  onSendReaction?: (emoji: string) => void;
  onOpenSettings?: () => void;
  onToggleChat: () => void;
  onTogglePeople: () => void;
  onLeave: () => void;
  onEndRoom: () => void;
}

export const MediaControlBar: React.FC<MediaControlBarProps> = ({
  micOn,
  cameraOn,
  isScreenSharing,
  isRecording,
  isRecordingLoading = false,
  isHandRaised = false,
  activePanel,
  participantCount,
  unreadChatCount = 0,
  isHost,
  isEnding,
  onToggleMic,
  onToggleCamera,
  onToggleScreenShare,
  onToggleRecording,
  onToggleHandRaise,
  onSendReaction,
  onOpenSettings,
  onToggleChat,
  onTogglePeople,
  onLeave,
  onEndRoom,
}) => {
  const [showEmojiPicker, setShowEmojiPicker] = useState(false);

  const emojis = ['👍', '👏', '❤️', '😂', '🎉'];

  const handleEmojiClick = (emoji: string) => {
    if (onSendReaction) onSendReaction(emoji);
    setShowEmojiPicker(false);
  };

  return (
    <div className="bg-[#102C4D] border border-[#1D4E78] p-4 rounded-2xl flex flex-wrap items-center justify-center gap-3 sm:gap-4 shadow-xl text-[#F8FAFC] relative">
      {/* Microphone Toggle Button */}
      <button
        onClick={onToggleMic}
        title={micOn ? 'Mute Microphone' : 'Unmute Microphone'}
        className={`p-3.5 rounded-xl border flex items-center space-x-2 text-[13px] font-semibold transition-all ${
          micOn
            ? 'bg-[#123456] border-[#1D4E78] text-[#F8FAFC] hover:bg-[#1A4570]'
            : 'bg-[#EF4444]/20 border-[#EF4444]/40 text-[#EF4444]'
        }`}
      >
        {micOn ? <Mic className="w-5 h-5 text-[#22C55E]" /> : <MicOff className="w-5 h-5 text-[#EF4444]" />}
        <span className="hidden sm:inline">{micOn ? 'Mute' : 'Unmute'}</span>
      </button>

      {/* Camera Toggle Button */}
      <button
        onClick={onToggleCamera}
        title={cameraOn ? 'Stop Video' : 'Start Video'}
        className={`p-3.5 rounded-xl border flex items-center space-x-2 text-[13px] font-semibold transition-all ${
          cameraOn
            ? 'bg-[#123456] border-[#1D4E78] text-[#F8FAFC] hover:bg-[#1A4570]'
            : 'bg-[#EF4444]/20 border-[#EF4444]/40 text-[#EF4444]'
        }`}
      >
        {cameraOn ? <Video className="w-5 h-5 text-[#3B82F6]" /> : <VideoOff className="w-5 h-5 text-[#EF4444]" />}
        <span className="hidden sm:inline">{cameraOn ? 'Stop Video' : 'Start Video'}</span>
      </button>

      {/* Screen Share Toggle Button */}
      <button
        onClick={onToggleScreenShare}
        title={isScreenSharing ? 'Stop Screen Sharing' : 'Start Screen Sharing'}
        className={`p-3.5 rounded-xl border flex items-center space-x-2 text-[13px] font-semibold transition-all ${
          isScreenSharing
            ? 'bg-[#EF4444]/20 border-[#EF4444]/40 text-[#EF4444]'
            : 'bg-[#123456] border-[#1D4E78] text-[#F8FAFC] hover:bg-[#1A4570]'
        }`}
      >
        {isScreenSharing ? (
          <>
            <StopCircle className="w-5 h-5 text-[#EF4444]" />
            <span className="hidden md:inline">Stop Share</span>
          </>
        ) : (
          <>
            <Monitor className="w-5 h-5 text-[#3B82F6]" />
            <span className="hidden md:inline">Share Screen</span>
          </>
        )}
      </button>

      {/* Hand Raise Toggle Button */}
      {onToggleHandRaise && (
        <button
          onClick={onToggleHandRaise}
          title={isHandRaised ? 'Lower Hand' : 'Raise Hand'}
          className={`p-3.5 rounded-xl border flex items-center space-x-2 text-[13px] font-semibold transition-all ${
            isHandRaised
              ? 'bg-[#F59E0B] border-[#F59E0B] text-white shadow-lg animate-bounce'
              : 'bg-[#123456] border-[#1D4E78] text-[#F8FAFC] hover:bg-[#1A4570]'
          }`}
        >
          <Hand className="w-5 h-5 text-[#F59E0B]" />
          <span className="hidden md:inline">{isHandRaised ? 'Lower Hand' : 'Raise Hand'}</span>
        </button>
      )}

      {/* Emoji Reactions Menu */}
      {onSendReaction && (
        <div className="relative">
          <button
            onClick={() => setShowEmojiPicker((prev) => !prev)}
            title="Send Reaction"
            className="p-3.5 rounded-xl border border-[#1D4E78] bg-[#123456] hover:bg-[#1A4570] text-[#F8FAFC] flex items-center space-x-2 text-[13px] font-semibold transition-all"
          >
            <Smile className="w-5 h-5 text-[#F59E0B]" />
            <span className="hidden md:inline">React</span>
          </button>

          {showEmojiPicker && (
            <div className="absolute bottom-16 left-1/2 transform -translate-x-1/2 bg-[#0A1B35] border border-[#1D4E78] p-2.5 rounded-2xl shadow-2xl flex items-center space-x-2 z-50 animate-fade-in">
              {emojis.map((emoji) => (
                <button
                  key={emoji}
                  onClick={() => handleEmojiClick(emoji)}
                  className="text-2xl p-2 hover:bg-[#123456] rounded-xl transition-all hover:scale-125"
                >
                  {emoji}
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Host Recording Control Button */}
      {isHost && (
        <button
          onClick={onToggleRecording}
          disabled={isRecordingLoading}
          title={isRecording ? 'Stop Recording' : 'Start Native Recording'}
          className={`p-3.5 rounded-xl border flex items-center space-x-2 text-[13px] font-semibold transition-all ${
            isRecording
              ? 'bg-[#EF4444] border-[#EF4444] text-white shadow-lg animate-pulse'
              : 'bg-[#123456] border-[#1D4E78] text-[#F8FAFC] hover:bg-[#1A4570]'
          }`}
        >
          <Radio className={`w-5 h-5 ${isRecording ? 'text-white' : 'text-[#EF4444]'}`} />
          <span className="hidden md:inline">{isRecording ? 'Stop REC' : 'Record'}</span>
        </button>
      )}

      {/* Device Settings Button */}
      {onOpenSettings && (
        <button
          onClick={onOpenSettings}
          title="Meeting Device Settings"
          className="p-3.5 rounded-xl border border-[#1D4E78] bg-[#123456] hover:bg-[#1A4570] text-[#F8FAFC] flex items-center space-x-2 text-[13px] font-semibold transition-all"
        >
          <Settings className="w-5 h-5 text-[#8FA4BD]" />
          <span className="hidden md:inline">Settings</span>
        </button>
      )}

      {/* Divider */}
      <div className="h-6 w-px bg-[#1D4E78] hidden sm:block mx-1" />

      {/* People Toggle Button */}
      <button
        onClick={onTogglePeople}
        title="View People Panel"
        className={`p-3.5 rounded-xl border flex items-center space-x-2 text-[13px] font-semibold transition-all relative ${
          activePanel === 'people'
            ? 'bg-[#3B82F6] border-[#3B82F6] text-white shadow-lg'
            : 'bg-[#123456] border-[#1D4E78] text-[#F8FAFC] hover:bg-[#1A4570]'
        }`}
      >
        <Users className="w-5 h-5" />
        <span className="hidden md:inline">People</span>
        <span className="ml-1 px-1.5 py-0.5 rounded-full bg-[#06152F] text-[11px] font-bold text-[#3B82F6] border border-[#1D4E78]">
          {participantCount}
        </span>
      </button>

      {/* In-Meeting Chat Toggle Button */}
      <button
        onClick={onToggleChat}
        title="View Meeting Chat"
        className={`p-3.5 rounded-xl border flex items-center space-x-2 text-[13px] font-semibold transition-all relative ${
          activePanel === 'chat'
            ? 'bg-[#3B82F6] border-[#3B82F6] text-white shadow-lg'
            : 'bg-[#123456] border-[#1D4E78] text-[#F8FAFC] hover:bg-[#1A4570]'
        }`}
      >
        <MessageSquare className="w-5 h-5" />
        <span className="hidden md:inline">Chat</span>
        {unreadChatCount > 0 && activePanel !== 'chat' && (
          <span className="absolute -top-1 -right-1 w-5 h-5 rounded-full bg-[#EF4444] text-white text-[10px] font-bold flex items-center justify-center border-2 border-[#102C4D] animate-bounce">
            {unreadChatCount > 9 ? '9+' : unreadChatCount}
          </span>
        )}
      </button>

      {/* Divider */}
      <div className="h-6 w-px bg-[#1D4E78] mx-1" />

      {/* Leave Room Button */}
      <Button variant="ghost" onClick={onLeave} icon={<PhoneOff />} size="md">
        Leave
      </Button>

      {/* Host End Meeting Button */}
      {isHost && (
        <Button variant="danger" onClick={onEndRoom} isLoading={isEnding} size="md">
          End Meeting
        </Button>
      )}
    </div>
  );
};
