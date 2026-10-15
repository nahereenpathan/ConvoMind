import React, { useEffect, useState } from 'react';
import { Trash2, RotateCcw, Sparkles, Calendar, Clock, Video, AlertCircle } from 'lucide-react';
import { meetingsApi } from '../api/meetings';
import { Meeting } from '../types';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { RestoreModal } from '../components/meetings/RestoreModal';
import { PermanentDeleteModal } from '../components/meetings/PermanentDeleteModal';
import { getErrorMessage } from '../utils/error';
import { useWorkspaceStore } from '../stores/useWorkspaceStore';

export const TrashPage: React.FC = () => {
  const { activeWorkspace } = useWorkspaceStore();
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [selectedMeeting, setSelectedMeeting] = useState<Meeting | null>(null);
  const [isRestoreOpen, setIsRestoreOpen] = useState(false);
  const [isPermanentDeleteOpen, setIsPermanentDeleteOpen] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [modalError, setModalError] = useState<string | null>(null);

  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const fetchTrashMeetings = async () => {
    setLoading(true);
    setError(null);
    try {
      const trashed = await meetingsApi.getTrashMeetings(
        activeWorkspace ? { workspace_id: activeWorkspace.id } : undefined
      );
      setMeetings(trashed);
    } catch (err: any) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTrashMeetings();
  }, [activeWorkspace?.id]);

  const handleOpenRestore = (meeting: Meeting) => {
    setSelectedMeeting(meeting);
    setIsRestoreOpen(true);
  };

  const handleOpenPermanentDelete = (meeting: Meeting) => {
    setSelectedMeeting(meeting);
    setModalError(null);
    setIsPermanentDeleteOpen(true);
  };

  const handleConfirmRestore = async () => {
    if (!selectedMeeting) return;
    setActionLoading(true);
    setModalError(null);
    try {
      await meetingsApi.restoreMeeting(selectedMeeting.id);
      setIsRestoreOpen(false);
      setToastMessage('Meeting restored successfully.');
      setTimeout(() => setToastMessage(null), 3000);
      fetchTrashMeetings();
    } catch (err: any) {
      alert(getErrorMessage(err));
    } finally {
      setActionLoading(false);
    }
  };

  const handleConfirmPermanentDelete = async () => {
    if (!selectedMeeting) return;
    setActionLoading(true);
    setModalError(null);
    try {
      await meetingsApi.permanentlyDeleteMeeting(selectedMeeting.id);
      setIsPermanentDeleteOpen(false);
      setToastMessage('Meeting permanently deleted.');
      setTimeout(() => setToastMessage(null), 3000);
      fetchTrashMeetings();
    } catch (err: any) {
      setModalError('Unable to permanently delete this meeting. Please try again.');
    } finally {
      setActionLoading(false);
    }
  };

  const formatDate = (dateStr?: string | null) => {
    if (!dateStr) return 'N/A';
    return new Date(dateStr).toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <div className="max-w-7xl mx-auto space-y-6 animate-fade-in text-[#F8FAFC]">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-[#102C4D] p-6 rounded-2xl border border-[#1D4E78] shadow-xl">
        <div className="space-y-1">
          <div className="flex items-center space-x-3">
            <div className="p-2.5 rounded-xl bg-[#EF4444]/20 border border-[#EF4444]/40 text-[#EF4444]">
              <Trash2 className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-[24px] sm:text-[28px] font-bold text-[#F8FAFC]">Trash</h1>
              <p className="text-[14px] text-[#B8C7DA]">
                Soft-deleted meetings that can be restored or permanently removed from your workspace.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Success Notification Toast */}
      {toastMessage && (
        <div className="p-4 rounded-xl bg-[#22C55E]/15 border border-[#22C55E]/40 text-[#22C55E] text-[14px] font-semibold animate-fade-in flex items-center space-x-2">
          <Sparkles className="w-5 h-5 shrink-0" />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Content Area */}
      {loading ? (
        <Card className="bg-[#102C4D] border border-[#1D4E78] p-6 shadow-xl space-y-4">
          <div className="animate-pulse space-y-4">
            <div className="h-10 bg-[#123456] rounded-xl w-full" />
            <div className="h-12 bg-[#123456] rounded-xl w-full" />
            <div className="h-12 bg-[#123456] rounded-xl w-full" />
            <div className="h-12 bg-[#123456] rounded-xl w-full" />
          </div>
        </Card>
      ) : error ? (
        <Card className="min-h-[40vh] flex flex-col items-center justify-center p-12 text-center space-y-4 bg-[#102C4D] border border-[#EF4444]/40 shadow-xl">
          <div className="w-16 h-16 rounded-full bg-[#EF4444]/15 border border-[#EF4444]/40 flex items-center justify-center text-[#EF4444]">
            <AlertCircle className="w-8 h-8" />
          </div>
          <div className="space-y-1 max-w-md">
            <h3 className="text-[18px] font-bold text-[#F8FAFC]">Unable to Load Trash</h3>
            <p className="text-[14px] text-[#B8C7DA]">
              {error || 'An error occurred while loading soft-deleted meetings. Please check your connection and try again.'}
            </p>
          </div>
          <Button
            variant="outline"
            size="md"
            onClick={fetchTrashMeetings}
            icon={<RotateCcw className="w-4 h-4 text-[#3B82F6]" />}
          >
            Retry API Request
          </Button>
        </Card>
      ) : meetings.length === 0 ? (
        <Card className="min-h-[40vh] flex flex-col items-center justify-center p-12 text-center space-y-4 bg-[#102C4D] border border-[#1D4E78] shadow-xl">
          <div className="w-16 h-16 rounded-full bg-[#123456] border border-[#1D4E78] flex items-center justify-center text-[#8FA4BD]">
            <Trash2 className="w-8 h-8 text-[#8FA4BD]" />
          </div>
          <div className="space-y-1 max-w-md">
            <h3 className="text-[18px] font-bold text-[#F8FAFC]">Trash is Empty</h3>
            <p className="text-[14px] text-[#B8C7DA]">
              No deleted meetings found. Any meetings you move to Trash will appear here for 30 days before permanent deletion.
            </p>
          </div>
        </Card>
      ) : (
        <Card className="bg-[#102C4D] border border-[#1D4E78] shadow-xl overflow-hidden rounded-2xl">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-[#1D4E78] bg-[#123456]/70 text-[12px] font-semibold text-[#8FA4BD] uppercase tracking-wider">
                  <th className="py-3.5 px-4 w-12 text-center">Icon</th>
                  <th className="py-3.5 px-4">Meeting Title</th>
                  <th className="py-3.5 px-4">Status</th>
                  <th className="py-3.5 px-4">Scheduled / Created</th>
                  <th className="py-3.5 px-4">Deleted At</th>
                  <th className="py-3.5 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#1D4E78] text-[14px]">
                {meetings.map((m) => (
                  <tr key={m.id} className="hover:bg-[#123456]/40 transition-colors">
                    <td className="py-4 px-4 text-center">
                      <div className="w-8 h-8 rounded-lg bg-[#EF4444]/15 border border-[#EF4444]/30 flex items-center justify-center text-[#EF4444] mx-auto">
                        <Video className="w-4 h-4" />
                      </div>
                    </td>
                    <td className="py-4 px-4 max-w-xs sm:max-w-md truncate">
                      <div className="font-semibold text-[#F8FAFC] truncate">{m.title}</div>
                      {m.description && (
                        <div className="text-[12px] text-[#8FA4BD] truncate">{m.description}</div>
                      )}
                    </td>
                    <td className="py-4 px-4 whitespace-nowrap">
                      <span className="px-2.5 py-1 rounded-full text-[11px] font-bold bg-[#EF4444]/20 border border-[#EF4444]/40 text-[#EF4444]">
                        In Trash
                      </span>
                    </td>
                    <td className="py-4 px-4 whitespace-nowrap text-[#B8C7DA] text-[13px]">
                      <div className="flex items-center space-x-1.5">
                        <Calendar className="w-3.5 h-3.5 text-[#8FA4BD]" />
                        <span>{formatDate(m.scheduled_at || m.created_at)}</span>
                      </div>
                    </td>
                    <td className="py-4 px-4 whitespace-nowrap text-[#B8C7DA] text-[13px]">
                      <div className="flex items-center space-x-1.5 text-[#EF4444]">
                        <Clock className="w-3.5 h-3.5" />
                        <span>{formatDate(m.deleted_at)}</span>
                      </div>
                    </td>
                    <td className="py-4 px-4 whitespace-nowrap text-right">
                      <div className="flex items-center justify-end space-x-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleOpenRestore(m)}
                          icon={<RotateCcw className="w-3.5 h-3.5 text-[#22C55E]" />}
                        >
                          Restore
                        </Button>
                        <Button
                          variant="danger"
                          size="sm"
                          onClick={() => handleOpenPermanentDelete(m)}
                          icon={<Trash2 className="w-3.5 h-3.5" />}
                        >
                          Delete Permanently
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* Restore Modal */}
      <RestoreModal
        isOpen={isRestoreOpen}
        meetingTitle={selectedMeeting?.title}
        isLoading={actionLoading}
        onClose={() => setIsRestoreOpen(false)}
        onConfirm={handleConfirmRestore}
      />

      {/* Permanent Delete Modal */}
      <PermanentDeleteModal
        isOpen={isPermanentDeleteOpen}
        meetingTitle={selectedMeeting?.title}
        isLoading={actionLoading}
        errorMessage={modalError}
        onClose={() => {
          setIsPermanentDeleteOpen(false);
          setModalError(null);
        }}
        onConfirm={handleConfirmPermanentDelete}
      />
    </div>
  );
};
