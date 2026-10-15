import React, { useEffect, useState } from 'react';
import { ShieldAlert, Radio } from 'lucide-react';

interface RecordingConsentBannerProps {
  startedAt?: string;
}

export const RecordingConsentBanner: React.FC<RecordingConsentBannerProps> = () => {
  const [seconds, setSeconds] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => {
      setSeconds((prev) => prev + 1);
    }, 1000);

    return () => clearInterval(timer);
  }, []);

  const formatTimer = (s: number) => {
    const mins = Math.floor(s / 60);
    const secs = s % 60;
    const pad = (n: number) => n.toString().padStart(2, '0');
    return `${pad(mins)}:${pad(secs)}`;
  };

  return (
    <div className="w-full bg-[#EF4444]/15 border border-[#EF4444]/40 px-4 py-2.5 rounded-xl flex items-center justify-between text-[13px] text-[#F8FAFC] shadow-lg animate-fade-in">
      <div className="flex items-center space-x-3">
        <div className="flex items-center space-x-1.5 px-2.5 py-0.5 rounded-full bg-[#EF4444] text-white text-[11px] font-bold tracking-wider uppercase shadow-md animate-pulse">
          <Radio className="w-3.5 h-3.5" />
          <span>REC</span>
        </div>

        <div className="flex items-center space-x-2">
          <span className="font-bold text-[#EF4444]">Recording Active</span>
          <span>•</span>
          <span className="text-[#B8C7DA]">
            Audio & Video are being recorded for AI intelligence and transcript synthesis.
          </span>
        </div>
      </div>

      <div className="flex items-center space-x-2 font-mono text-[#EF4444] font-bold shrink-0">
        <ShieldAlert className="w-4 h-4 text-[#EF4444]" />
        <span>{formatTimer(seconds)}</span>
      </div>
    </div>
  );
};
