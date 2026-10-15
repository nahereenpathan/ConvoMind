import React, { useEffect } from 'react';
import { X } from 'lucide-react';

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title?: string;
  description?: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
  maxWidth?: 'sm' | 'md' | 'lg' | 'xl' | '2xl' | '3xl' | '720px';
}

export const Modal: React.FC<ModalProps> = ({
  isOpen,
  onClose,
  title,
  description,
  children,
  footer,
  maxWidth = 'md',
}) => {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    if (isOpen) {
      document.body.style.overflow = 'hidden';
      window.addEventListener('keydown', handleKeyDown);
    }
    return () => {
      document.body.style.overflow = 'unset';
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const maxWidths = {
    sm: 'max-w-sm',
    md: 'max-w-md',
    lg: 'max-w-lg',
    xl: 'max-w-xl',
    '2xl': 'max-w-2xl',
    '3xl': 'max-w-3xl',
    '720px': 'max-w-[720px]',
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 bg-[#06152F]/85 backdrop-blur-sm animate-fade-in">
      <div
        className={`w-full ${maxWidths[maxWidth]} bg-[#102C4D] border border-[#1D4E78] rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh] text-[#F8FAFC]`}
        onClick={(e) => e.stopPropagation()}
      >
        {(title || description) && (
          <div className="flex items-start justify-between p-4 sm:p-5 border-b border-[#1D4E78] bg-[#0B2342] shrink-0">
            <div>
              {title && <h3 className="text-[18px] sm:text-[20px] font-bold text-[#F8FAFC]">{title}</h3>}
              {description && <p className="text-[13px] text-[#8FA4BD] mt-0.5">{description}</p>}
            </div>
            <button
              onClick={onClose}
              type="button"
              aria-label="Close modal"
              className="text-[#8FA4BD] hover:text-[#F8FAFC] hover:bg-[#123456] p-1.5 rounded-lg transition-colors ml-4 shrink-0"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        )}
        <div className="p-4 sm:p-5 overflow-y-auto custom-scrollbar flex-1 min-h-0 text-[#F8FAFC]">
          {children}
        </div>
        {footer && (
          <div className="p-4 sm:p-5 border-t border-[#1D4E78] bg-[#0B2342] shrink-0 flex items-center justify-between">
            {footer}
          </div>
        )}
      </div>
    </div>
  );
};
