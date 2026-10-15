import React, { useEffect, useState } from 'react';
import { mediaService } from '../../services/mediaService';

interface FloatingEmoji {
  id: string;
  senderName: string;
  emoji: string;
  leftOffset: number;
}

interface ReactionsOverlayProps {
  reaction?: string | null;
}

export const ReactionsOverlay: React.FC<ReactionsOverlayProps> = () => {
  const [reactions, setReactions] = useState<FloatingEmoji[]>([]);

  useEffect(() => {
    const unsub = mediaService.subscribeReaction((data) => {
      const newEmoji: FloatingEmoji = {
        id: Math.random().toString(36).substring(2, 9),
        senderName: data.senderName || 'Participant',
        emoji: data.emoji,
        leftOffset: Math.floor(Math.random() * 70) + 15, // 15% to 85% width
      };

      setReactions((prev) => [...prev, newEmoji]);

      setTimeout(() => {
        setReactions((prev) => prev.filter((r) => r.id !== newEmoji.id));
      }, 3500);
    });

    return unsub;
  }, []);

  if (reactions.length === 0) return null;

  return (
    <div className="absolute inset-0 pointer-events-none z-30 overflow-hidden">
      {reactions.map((r) => (
        <div
          key={r.id}
          style={{ left: `${r.leftOffset}%` }}
          className="absolute bottom-16 flex flex-col items-center animate-bounce transition-all duration-1000 transform -translate-x-1/2"
        >
          <div className="bg-[#102C4D]/90 border border-[#3B82F6]/50 text-white text-[12px] font-bold px-2 py-0.5 rounded-full shadow-lg mb-1 backdrop-blur-sm">
            {r.senderName}
          </div>
          <span className="text-[36px] drop-shadow-xl animate-pulse">{r.emoji}</span>
        </div>
      ))}
    </div>
  );
};
