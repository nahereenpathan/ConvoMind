import React, { useEffect, useState, useCallback } from 'react';
import { RefreshCw, WifiOff } from 'lucide-react';
import { api } from '../../api/client';

export const BackendHealthIndicator: React.FC = () => {
  const [status, setStatus] = useState<'online' | 'connecting' | 'offline'>('online');
  const [attempt, setAttempt] = useState(0);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const checkHealth = useCallback(async () => {
    try {
      // Direct call to /health endpoint
      await api.get('/health', {
        headers: { 'Cache-Control': 'no-cache' },
      });
      setStatus('online');
      setErrorMessage(null);
      setAttempt(0);
    } catch (err: any) {
      console.warn('[Health Check] Status check failed:', err?.response?.status || err?.code || err?.message);
      if (err.response?.status === 503) {
        setStatus('connecting');
        setErrorMessage('Backend API service is initializing...');
      } else if (!err.response || err.code === 'ERR_NETWORK') {
        setStatus('connecting');
        setErrorMessage('Connecting to ConvoMind backend service...');
      } else {
        // HTTP 200-499 means backend is up and running
        setStatus('online');
        setErrorMessage(null);
      }
    }
  }, []);

  useEffect(() => {
    checkHealth();
  }, [checkHealth]);

  // Exponential backoff reconnect retry loop when in connecting state
  useEffect(() => {
    if (status !== 'connecting') return;

    if (attempt >= 5) {
      setStatus('offline');
      setErrorMessage('Backend server (FastAPI on port 8000) is unreachable. Please verify server status.');
      return;
    }

    const backoffDelay = Math.min(2000 * Math.pow(1.5, attempt), 10000);
    const timer = setTimeout(() => {
      setAttempt((prev) => prev + 1);
      checkHealth();
    }, backoffDelay);

    return () => clearTimeout(timer);
  }, [status, attempt, checkHealth]);

  if (status === 'online') {
    return null;
  }

  return (
    <div className="bg-[#0F2942] border-b border-[#1D4E78] px-4 py-2.5 text-[13px] flex items-center justify-between shadow-md animate-fade-in">
      <div className="flex items-center space-x-2.5">
        {status === 'connecting' ? (
          <div className="p-1 rounded-full bg-[#3B82F6]/20 text-[#3B82F6]">
            <RefreshCw className="w-4 h-4 animate-spin" />
          </div>
        ) : (
          <div className="p-1 rounded-full bg-[#EF4444]/20 text-[#EF4444]">
            <WifiOff className="w-4 h-4" />
          </div>
        )}
        <span className="font-medium text-[#F8FAFC]">
          {errorMessage || 'Connecting to ConvoMind backend...'}
        </span>
        {status === 'connecting' && (
          <span className="text-[11px] text-[#8FA4BD] bg-[#123456] px-2 py-0.5 rounded-full border border-[#1D4E78]">
            Attempt {attempt + 1} of 5
          </span>
        )}
      </div>

      <button
        onClick={() => {
          setStatus('connecting');
          setAttempt(0);
          checkHealth();
        }}
        className="flex items-center space-x-1.5 px-3 py-1 bg-[#123456] hover:bg-[#1D4E78] text-[#F8FAFC] border border-[#1D4E78] rounded-lg text-[12px] font-semibold transition-colors"
      >
        <RefreshCw className="w-3.5 h-3.5" />
        <span>Retry Connection</span>
      </button>
    </div>
  );
};
