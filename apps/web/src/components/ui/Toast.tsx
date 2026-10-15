import React, { useEffect } from 'react';
import { CheckCircle2, AlertCircle, Info, X } from 'lucide-react';
import { getErrorMessage } from '../../utils/error';

export type ToastType = 'success' | 'error' | 'info';

interface ToastProps {
  message: any;
  type?: ToastType;
  onClose: () => void;
  duration?: number;
}

export const Toast: React.FC<ToastProps> = ({
  message,
  type = 'info',
  onClose,
  duration = 4000,
}) => {
  useEffect(() => {
    const timer = setTimeout(() => {
      onClose();
    }, duration);
    return () => clearTimeout(timer);
  }, [onClose, duration]);

  const icons = {
    success: <CheckCircle2 className="w-5 h-5 text-emerald-400" />,
    error: <AlertCircle className="w-5 h-5 text-rose-400" />,
    info: <Info className="w-5 h-5 text-sky-400" />,
  };

  const borders = {
    success: 'border-emerald-500/40 bg-emerald-950/90 text-emerald-100',
    error: 'border-rose-500/40 bg-rose-950/90 text-rose-100',
    info: 'border-sky-500/40 bg-sky-950/90 text-sky-100',
  };

  return (
    <div
      className={`fixed bottom-5 right-5 z-50 flex items-center space-x-3 px-4 py-3 border rounded-xl shadow-xl backdrop-blur-md animate-fade-in ${borders[type]}`}
    >
      {icons[type]}
      <p className="text-sm font-medium">{getErrorMessage(message)}</p>
      <button onClick={onClose} className="p-1 rounded-md hover:bg-white/10 text-slate-400 hover:text-white">
        <X className="w-4 h-4" />
      </button>
    </div>
  );
};
