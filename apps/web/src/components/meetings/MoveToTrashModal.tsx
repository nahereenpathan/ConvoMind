import React from 'react';
import { Trash2, AlertTriangle } from 'lucide-react';
import { Modal } from '../ui/Modal';
import { Button } from '../ui/Button';

interface MoveToTrashModalProps {
  isOpen: boolean;
  meetingTitle?: string;
  isLoading?: boolean;
  onClose: () => void;
  onConfirm: () => void;
}

export const MoveToTrashModal: React.FC<MoveToTrashModalProps> = ({
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
      title="Move meeting to Trash?"
      description="You can restore this meeting later from Trash."
      maxWidth="md"
    >
      <div className="space-y-4 py-2 text-[#F8FAFC]">
        <div className="p-4 rounded-xl bg-[#123456] border border-[#1D4E78] space-y-2">
          <div className="flex items-center space-x-2 text-[#F59E0B] font-semibold text-[14px]">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>Target Meeting</span>
          </div>
          <p className="text-[16px] font-bold text-[#F8FAFC] truncate">
            "{meetingTitle || 'Untitled Meeting'}"
          </p>
          <p className="text-[13px] text-[#B8C7DA]">
            This meeting will be hidden from active lists and dashboard analytics. All recordings, transcripts, and AI insights will be safely preserved in Trash.
          </p>
        </div>

        <div className="flex items-center justify-end space-x-3 pt-3 border-t border-[#1D4E78]">
          <Button variant="ghost" onClick={onClose} disabled={isLoading}>
            Cancel
          </Button>
          <Button
            variant="danger"
            onClick={onConfirm}
            isLoading={isLoading}
            icon={<Trash2 className="w-4 h-4" />}
          >
            {isLoading ? 'Moving...' : 'Move to Trash'}
          </Button>
        </div>
      </div>
    </Modal>
  );
};
