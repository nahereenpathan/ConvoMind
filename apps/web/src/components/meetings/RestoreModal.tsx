import React from 'react';
import { RotateCcw } from 'lucide-react';
import { Modal } from '../ui/Modal';
import { Button } from '../ui/Button';

interface RestoreModalProps {
  isOpen: boolean;
  meetingTitle?: string;
  isLoading?: boolean;
  onClose: () => void;
  onConfirm: () => void;
}

export const RestoreModal: React.FC<RestoreModalProps> = ({
  isOpen,
  meetingTitle,
  isLoading = false,
  onClose,
  onConfirm,
}) => {
  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Restore Meeting?"
      description="Return this meeting back to active status."
      maxWidth="md"
    >
      <div className="space-y-4 py-2 text-[#F8FAFC]">
        <div className="p-4 rounded-xl bg-[#123456] border border-[#1D4E78] space-y-2">
          <p className="text-[16px] font-bold text-[#F8FAFC] truncate">
            "{meetingTitle || 'Untitled Meeting'}"
          </p>
          <p className="text-[13px] text-[#B8C7DA]">
            This meeting will return to your active meetings list, dashboard analytics, and AI search results.
          </p>
        </div>

        <div className="flex items-center justify-end space-x-3 pt-3 border-t border-[#1D4E78]">
          <Button variant="ghost" onClick={onClose} disabled={isLoading}>
            Cancel
          </Button>
          <Button
            onClick={onConfirm}
            isLoading={isLoading}
            icon={<RotateCcw className="w-4 h-4" />}
          >
            {isLoading ? 'Restoring...' : 'Restore'}
          </Button>
        </div>
      </div>
    </Modal>
  );
};
