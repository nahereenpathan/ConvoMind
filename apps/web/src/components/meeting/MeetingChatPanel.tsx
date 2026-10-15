import React, { useEffect, useRef, useState } from 'react';
import { Send, X, MessageSquare } from 'lucide-react';
import { MeetingChatMessage } from '../../types';
import { meetingsApi } from '../../api/meetings';
import { mediaService } from '../../services/mediaService';

interface MeetingChatPanelProps {
  meetingId: string;
  currentUserId: string;
  currentUserName: string;
  onClose: () => void;
}

export const MeetingChatPanel: React.FC<MeetingChatPanelProps> = ({
  meetingId,
  currentUserId,
  currentUserName,
  onClose,
}) => {
  const [messages, setMessages] = useState<MeetingChatMessage[]>([]);
  const [text, setText] = useState('');
  const [sending, setSending] = useState(false);
  const [loading, setLoading] = useState(true);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Load chat history on mount
  useEffect(() => {
    let active = true;

    const loadChatHistory = async () => {
      setLoading(true);
      try {
        const history = await meetingsApi.getMeetingMessages(meetingId);
        if (active) setMessages(history);
      } catch (e) {
        console.warn('[MeetingChatPanel] Load history error:', e);
      } finally {
        if (active) setLoading(false);
      }
    };

    loadChatHistory();

    return () => {
      active = false;
    };
  }, [meetingId]);

  // Subscribe to incoming live broadcast chat messages
  useEffect(() => {
    const unsub = mediaService.subscribeChatMessage((incomingMsg) => {
      setMessages((prev) => {
        if (prev.some((m) => m.id === incomingMsg.id)) return prev;
        return [...prev, incomingMsg];
      });
    });

    return () => unsub();
  }, []);

  // Auto-scroll to bottom on message list updates
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    const cleanText = text.trim();
    if (!cleanText || sending) return;

    setSending(true);
    try {
      // 1. Save message to backend database
      const savedMsg = await meetingsApi.sendMeetingMessage(meetingId, cleanText);

      // 2. Broadcast via LiveKit Data Channel
      await mediaService.broadcastChatMessage(savedMsg);

      setText('');
    } catch (err: any) {
      console.error('[MeetingChatPanel] Send error:', err);
    } finally {
      setSending(false);
    }
  };

  const formatTime = (isoString?: string) => {
    if (!isoString) return '';
    try {
      const d = new Date(isoString);
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch {
      return '';
    }
  };

  return (
    <div className="w-full md:w-80 lg:w-96 bg-[#102C4D] border border-[#1D4E78] rounded-2xl flex flex-col h-[520px] shadow-2xl overflow-hidden text-[#F8FAFC]">
      {/* Header */}
      <div className="p-4 bg-[#06152F] border-b border-[#1D4E78] flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <MessageSquare className="w-4 h-4 text-[#3B82F6]" />
          <h3 className="text-[16px] font-bold text-[#F8FAFC]">Meeting Chat</h3>
        </div>
        <button
          onClick={onClose}
          className="text-[#8FA4BD] hover:text-[#F8FAFC] transition-colors p-1"
          title="Close Chat"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Messages List Area */}
      <div ref={scrollRef} className="flex-1 p-4 space-y-3 overflow-y-auto">
        {loading ? (
          <div className="flex flex-col items-center justify-center h-full space-y-2 text-[#8FA4BD]">
            <div className="w-6 h-6 border-2 border-[#3B82F6] border-t-transparent rounded-full animate-spin" />
            <p className="text-[12px]">Loading messages...</p>
          </div>
        ) : messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center space-y-2 text-[#8FA4BD] p-4">
            <MessageSquare className="w-8 h-8 opacity-40" />
            <p className="text-[14px] font-semibold text-[#F8FAFC]">No Messages Yet</p>
            <p className="text-[12px]">Send a message to start the meeting conversation.</p>
          </div>
        ) : (
          messages.map((msg) => {
            const isMe = msg.sender_id === currentUserId || msg.sender_name === currentUserName;
            return (
              <div
                key={msg.id || `${msg.created_at}-${msg.sender_name}`}
                className={`flex flex-col ${isMe ? 'items-end' : 'items-start'}`}
              >
                <div className="flex items-center space-x-2 text-[11px] text-[#8FA4BD] mb-1 px-1">
                  <span className="font-semibold text-[#B8C7DA]">
                    {isMe ? 'You' : msg.sender_name}
                  </span>
                  <span>•</span>
                  <span>{formatTime(msg.created_at)}</span>
                </div>

                <div
                  className={`max-w-[85%] rounded-2xl px-3.5 py-2.5 text-[13px] leading-relaxed break-words shadow-md ${
                    isMe
                      ? 'bg-[#2563EB] text-white rounded-tr-none'
                      : 'bg-[#123456] text-[#F8FAFC] border border-[#1D4E78] rounded-tl-none'
                  }`}
                >
                  {msg.message}
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Message Input Form */}
      <form onSubmit={handleSendMessage} className="p-3 bg-[#06152F] border-t border-[#1D4E78]">
        <div className="flex items-center space-x-2">
          <input
            type="text"
            placeholder="Type a message..."
            value={text}
            onChange={(e) => setText(e.target.value)}
            maxLength={1000}
            className="flex-1 bg-[#123456] border border-[#1D4E78] rounded-xl px-3.5 py-2 text-[13px] text-[#F8FAFC] placeholder-[#8FA4BD] focus:outline-none focus:border-[#3B82F6]"
          />
          <button
            type="submit"
            disabled={!text.trim() || sending}
            className="p-2.5 rounded-xl bg-[#3B82F6] hover:bg-[#2563EB] text-white disabled:opacity-50 disabled:cursor-not-allowed transition-all shrink-0"
            title="Send Message"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </form>
    </div>
  );
};
