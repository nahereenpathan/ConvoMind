import React, { useState, useEffect, useRef } from 'react';
import { Send, Bot, User, Sparkles, BookOpen, ChevronDown, ChevronUp } from 'lucide-react';
import { ChatMessage } from '../../types';
import { chatApi } from '../../api/chat';
import { Button } from '../ui/Button';
import { getErrorMessage } from '../../utils/error';

interface ChatContainerProps {
  meetingId: string;
}

export const ChatContainer: React.FC<ChatContainerProps> = ({ meetingId }) => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [expandedCitations, setExpandedCitations] = useState<Record<number, boolean>>({});
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setMessages([]);
    const fetchHistory = async () => {
      try {
        const history = await chatApi.getHistory(meetingId);
        setMessages(history);
      } catch (err) {
        console.error('Failed to fetch chat history', err);
      }
    };
    fetchHistory();
  }, [meetingId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || loading) return;

    const userQuery = input.trim();
    setInput('');

    // Optimistic user message
    const tempUserMsg: ChatMessage = {
      id: `temp-${Date.now()}`,
      role: 'user',
      content: userQuery,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, tempUserMsg]);
    setLoading(true);

    try {
      const response = await chatApi.sendMessage(meetingId, userQuery);
      const botMsg: ChatMessage = {
        id: `bot-${Date.now()}`,
        role: 'assistant',
        content: response.answer,
        citations: response.citations,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, botMsg]);
    } catch (err) {
      console.error('Failed to send message', err);
      const errorMsg: ChatMessage = {
        id: `err-${Date.now()}`,
        role: 'assistant',
        content: 'Sorry, I encountered an error searching this meeting transcript.',
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  };

  const toggleCitation = (index: number) => {
    setExpandedCitations((prev) => ({ ...prev, [index]: !prev[index] }));
  };

  return (
    <div className="flex flex-col h-[650px] bg-[#102C4D] border border-[#1D4E78] rounded-2xl overflow-hidden shadow-xl text-[#F8FAFC]">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3.5 border-b border-[#1D4E78] bg-[#0B2342]">
        <div className="flex items-center space-x-2.5">
          <div className="p-2 rounded-lg bg-[#6366F1]/20 text-[#818CF8] border border-[#6366F1]/40">
            <Bot className="w-4 h-4" />
          </div>
          <div>
            <h4 className="text-[15px] sm:text-[16px] font-semibold text-[#F8FAFC]">Meeting RAG Assistant</h4>
            <p className="text-[12px] text-[#8FA4BD]">Ask any question about this meeting transcript</p>
          </div>
        </div>
      </div>

      {/* Messages Area */}
      <div className="flex-1 p-5 overflow-y-auto custom-scrollbar space-y-4">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center text-[#8FA4BD] space-y-3">
            <Sparkles className="w-8 h-8 text-[#8FA4BD]" />
            <p className="text-[13px] sm:text-[14px] max-w-xs">
              Ask questions like "What were the main budget decisions?" or "What did Alice say about deadlines?"
            </p>
          </div>
        ) : (
          messages.map((msg, idx) => (
            <div
              key={msg.id || idx}
              className={`flex items-start space-x-3 ${msg.role === 'user' ? 'flex-row-reverse space-x-reverse' : ''}`}
            >
              <div
                className={`p-2 rounded-lg shrink-0 ${
                  msg.role === 'user'
                    ? 'bg-[#2563EB] text-white'
                    : 'bg-[#6366F1]/20 border border-[#6366F1]/40 text-[#818CF8]'
                }`}
              >
                {msg.role === 'user' ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
              </div>

              <div className={`max-w-[80%] space-y-2`}>
                <div
                  className={`p-4 rounded-2xl text-[15px] sm:text-[16px] leading-[1.6] ${
                    msg.role === 'user'
                      ? 'bg-[#2563EB] text-white rounded-tr-none shadow-md font-medium'
                      : 'bg-[#123456] border border-[#1D4E78] text-[#F8FAFC] rounded-tl-none shadow-md font-normal'
                  }`}
                >
                  {getErrorMessage(msg.content)}
                </div>

                {/* Citations */}
                {msg.citations && msg.citations.length > 0 && (
                  <div className="mt-2 bg-[#0B2342] border border-[#1D4E78] rounded-xl p-3 space-y-2">
                    <button
                      onClick={() => toggleCitation(idx)}
                      className="flex items-center justify-between w-full text-[13px] sm:text-[14px] font-semibold text-[#B8C7DA] hover:text-[#F8FAFC]"
                    >
                      <span className="flex items-center space-x-1.5">
                        <BookOpen className="w-4 h-4 text-[#818CF8]" />
                        <span>Sources & Citations ({msg.citations.length})</span>
                      </span>
                      {expandedCitations[idx] ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                    </button>

                    {expandedCitations[idx] && (
                      <div className="space-y-2 pt-2 border-t border-[#1D4E78]">
                        {msg.citations.map((cite, cIdx) => {
                          const speakerName = cite.speaker || (cite.speaker_labels && cite.speaker_labels.length > 0 ? cite.speaker_labels.join(', ') : 'Speaker');
                          const rawScore = cite.score ?? cite.similarity_score ?? 0;
                          const scorePct = Math.min(100, Math.max(0, Math.round(rawScore * 100)));
                          const textContent = cite.text || cite.text_excerpt || '';

                          const formatTs = (sec?: number) => {
                            if (sec === undefined || sec === null) return null;
                            const m = Math.floor(sec / 60);
                            const s = Math.floor(sec % 60);
                            return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
                          };

                          const timeStr = cite.start_time !== undefined && cite.end_time !== undefined
                            ? `${formatTs(cite.start_time)} - ${formatTs(cite.end_time)}`
                            : null;

                          return (
                            <div key={cIdx} className="text-[13px] sm:text-[14px] bg-[#102C4D] p-3 rounded-lg border border-[#1D4E78] shadow-sm space-y-1">
                              <div className="flex items-center justify-between text-[#B8C7DA] font-medium">
                                <span className="font-semibold text-[#F8FAFC]">
                                  {speakerName} {timeStr ? `(${timeStr})` : ''}
                                </span>
                                <span className="text-[12px] font-bold text-[#818CF8] bg-[#6366F1]/20 px-2 py-0.5 rounded border border-[#6366F1]/40">
                                  Score: {scorePct}%
                                </span>
                              </div>
                              <p className="text-[#B8C7DA] italic leading-[1.5]">"{textContent}"</p>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          ))
        )}

        {loading && (
          <div className="flex items-start space-x-3">
            <div className="p-2 rounded-lg bg-[#6366F1]/20 border border-[#6366F1]/40 text-[#818CF8] shrink-0">
              <Bot className="w-4 h-4 animate-spin" />
            </div>
            <div className="p-4 rounded-2xl bg-[#123456] border border-[#1D4E78] text-[13px] sm:text-[14px] text-[#B8C7DA] animate-pulse">
              Searching transcript vector embeddings...
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <form onSubmit={handleSend} className="p-4 border-t border-[#1D4E78] bg-[#0B2342] flex items-center space-x-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask something about this meeting..."
          className="flex-1 bg-[#123456] border border-[#1D4E78] rounded-xl px-4 py-2.5 text-[14px] sm:text-[15px] text-[#F8FAFC] placeholder-[#8FA4BD] focus:outline-none focus:border-[#3B82F6]"
          disabled={loading}
        />
        <Button type="submit" disabled={!input.trim() || loading} icon={<Send />}>
          Send
        </Button>
      </form>
    </div>
  );
};
