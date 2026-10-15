import React, { useState, useEffect } from 'react';
import { Search, Plus, Filter, Video } from 'lucide-react';
import { useWorkspaceStore } from '../stores/useWorkspaceStore';
import { meetingsApi } from '../api/meetings';
import { Meeting, MeetingStatus } from '../types';
import { MeetingCard } from '../components/meetings/MeetingCard';
import { CreateMeetingModal } from '../components/meetings/CreateMeetingModal';
import { MoveToTrashModal } from '../components/meetings/MoveToTrashModal';
import { Input } from '../components/ui/Input';
import { Button } from '../components/ui/Button';
import { Skeleton } from '../components/ui/Skeleton';
import { Card } from '../components/ui/Card';
import { getErrorMessage } from '../utils/error';

export const MeetingsListPage: React.FC = () => {
  const { activeWorkspace } = useWorkspaceStore();
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [isModalOpen, setIsModalOpen] = useState(false);

  // Soft delete state
  const [selectedMeeting, setSelectedMeeting] = useState<Meeting | null>(null);
  const [isTrashModalOpen, setIsTrashModalOpen] = useState(false);
  const [trashLoading, setTrashLoading] = useState(false);

  const fetchMeetings = async () => {
    if (!activeWorkspace) {
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const data = await meetingsApi.getMeetings({
        workspace_id: activeWorkspace.id,
        status: statusFilter !== 'ALL' ? (statusFilter as MeetingStatus) : undefined,
        search: search.trim() || undefined,
      });
      setMeetings(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error('Failed to fetch meetings', err);
      setMeetings([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMeetings();
  }, [activeWorkspace, statusFilter, search]);

  const handleOpenTrashModal = (meeting: Meeting) => {
    setSelectedMeeting(meeting);
    setIsTrashModalOpen(true);
  };

  const handleConfirmMoveToTrash = async () => {
    if (!selectedMeeting) return;
    setTrashLoading(true);
    try {
      await meetingsApi.moveToTrash(selectedMeeting.id);
      setIsTrashModalOpen(false);
      fetchMeetings();
    } catch (err: any) {
      alert(getErrorMessage(err));
    } finally {
      setTrashLoading(false);
    }
  };

  const safeMeetings = Array.isArray(meetings) ? meetings : [];

  return (
    <div className="space-y-6 animate-fade-in text-[#F8FAFC]">
      <CreateMeetingModal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} />

      <MoveToTrashModal
        isOpen={isTrashModalOpen}
        meetingTitle={selectedMeeting?.title}
        isLoading={trashLoading}
        onClose={() => setIsTrashModalOpen(false)}
        onConfirm={handleConfirmMoveToTrash}
      />

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-[26px] sm:text-[30px] font-bold text-[#F8FAFC]">Workspace Meetings</h1>
          <p className="text-[14px] sm:text-[15px] text-[#B8C7DA] mt-1">
            Manage meeting recordings, transcriptions, speaker maps, and AI insights.
          </p>
        </div>
        <Button onClick={() => setIsModalOpen(true)} icon={<Plus />}>
          New Meeting
        </Button>
      </div>

      {/* Search & Filters */}
      <div className="flex flex-col sm:flex-row items-center gap-3">
        <div className="w-full sm:w-80">
          <Input
            placeholder="Search meetings by title..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            icon={<Search className="w-4 h-4 text-[#8FA4BD]" />}
          />
        </div>

        <div className="flex items-center space-x-2 w-full sm:w-auto">
          <Filter className="w-4 h-4 text-[#8FA4BD]" />
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="bg-[#123456] border border-[#1D4E78] text-[#F8FAFC] text-[13px] sm:text-[14px] rounded-lg px-3 py-2 shadow-sm focus:outline-none focus:border-[#3B82F6] font-medium"
          >
            <option value="ALL">All Statuses</option>
            <option value={MeetingStatus.COMPLETED}>Completed</option>
            <option value={MeetingStatus.PROCESSING}>Processing</option>
            <option value={MeetingStatus.SCHEDULED}>Scheduled</option>
            <option value={MeetingStatus.FAILED}>Failed</option>
          </select>
        </div>
      </div>

      {/* Grid List */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          <Skeleton className="h-44" />
          <Skeleton className="h-44" />
          <Skeleton className="h-44" />
        </div>
      ) : safeMeetings.length === 0 ? (
        <Card className="p-12 text-center text-[#8FA4BD] space-y-3 bg-[#102C4D] border border-[#1D4E78]">
          <Video className="w-10 h-10 text-[#8FA4BD] mx-auto" />
          <p className="text-[15px] font-semibold text-[#F8FAFC]">No meetings match your query</p>
          <p className="text-[13px] text-[#8FA4BD]">Try adjusting your search terms or filter selection.</p>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {safeMeetings.map((meeting) => (
            <MeetingCard
              key={meeting.id}
              meeting={meeting}
              onMoveToTrash={handleOpenTrashModal}
            />
          ))}
        </div>
      )}
    </div>
  );
};
