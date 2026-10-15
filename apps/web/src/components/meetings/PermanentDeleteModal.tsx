import React, { useState, useEffect } from 'react';
import { AlertOctagon, Trash2 } from 'lucide-react';
import { Modal } from '../ui/Modal';
import { Button } from '../ui/Button';

interface PermanentDeleteModalProps {
  isOpen: boolean;
  meetingTitle?: string;
  isLoading?: boolean;
  errorMessage?: string | null;
  onClose: () => void;
  onConfirm: () => void;
}

export const PermanentDeleteModal: React.FC<PermanentDeleteModalProps> = ({
  isOpen,
  meetingTitle,
  isLoading = false,
  errorMessage,
  onClose,
  onConfirm,
}) => {
  const [confirmInput, setConfirmInput] = useState('');

  useEffect(() => {
    if (isOpen) {
      setConfirmInput('');
    }
  }, [isOpen]);

  // Strict exact comparison: must match "DELETE" exactly (case-sensitive, no spaces allowed)
  const isConfirmed = confirmInput === 'DELETE';

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (isConfirmed && !isLoading) {
      onConfirm();
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Permanently Delete Meeting?"
      description="This action cannot be undone."
      maxWidth="md"
    >
      <form onSubmit={handleSubmit} className="space-y-4 py-2 text-[#F8FAFC]">
        <div className="p-4 rounded-xl bg-[#EF4444]/15 border border-[#EF4444]/40 space-y-2">
          <div className="flex items-center space-x-2 text-[#EF4444] font-semibold text-[14px]">
            <AlertOctagon className="w-4 h-4 shrink-0" />
            <span>Destructive Action Warning</span>
          </div>
          <p className="text-[16px] font-bold text-[#F8FAFC] truncate">
            "{meetingTitle || 'Untitled Meeting'}"
          </p>
          <p className="text-[13px] text-[#B8C7DA] leading-relaxed">
            The meeting, audio recordings, transcripts, AI insights, action items, decisions, questions, and pgvector embeddings will be permanently deleted from database and storage.
          </p>
        </div>

        {errorMessage && (
          <div className="p-3 rounded-lg bg-[#EF4444]/20 border border-[#EF4444]/50 text-[#EF4444] text-[13px]">
            {errorMessage}
          </div>
        )}

        <div className="space-y-2">
          <label className="text-[13px] font-semibold text-[#B8C7DA]">
            Type <span className="font-mono text-[#EF4444] font-bold">DELETE</span> to confirm:
          </label>
          <input
            type="text"
            value={confirmInput}
            onChange={(e) => setConfirmInput(e.target.value)}
            placeholder="DELETE"
            disabled={isLoading}
            autoFocus
            className="w-full bg-[#123456] border border-[#1D4E78] text-[#F8FAFC] rounded-lg p-3 font-mono text-[14px] focus:outline-none focus:border-[#EF4444] disabled:opacity-50"
          />
        </div>

        <div className="flex items-center justify-end space-x-3 pt-3 border-t border-[#1D4E78]">
          <Button variant="ghost" onClick={onClose} disabled={isLoading} type="button">
            Cancel
          </Button>
          <Button
            variant="danger"
            type="submit"
            disabled={!isConfirmed || isLoading}
            isLoading={isLoading}
            icon={<Trash2 className="w-4 h-4" />}
          >
            {isLoading ? 'Deleting...' : 'Delete Permanently'}
          </Button>
        </div>
      </form>
    </Modal>
  );
};
