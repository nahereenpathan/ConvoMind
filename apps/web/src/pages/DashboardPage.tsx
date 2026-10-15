import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Video, CheckSquare, Sparkles, Plus, ChevronRight, Clock } from 'lucide-react';
import { useWorkspaceStore } from '../stores/useWorkspaceStore';
import { meetingsApi } from '../api/meetings';
import { Meeting } from '../types';
import { MeetingCard } from '../components/meetings/MeetingCard';
import { CreateMeetingModal } from '../components/meetings/CreateMeetingModal';
import { MoveToTrashModal } from '../components/meetings/MoveToTrashModal';
import { Button } from '../components/ui/Button';
import { Skeleton } from '../components/ui/Skeleton';
import { Card } from '../components/ui/Card';
import { getErrorMessage } from '../utils/error';

import { intelligenceApi } from '../api/intelligence';

export const DashboardPage: React.FC = () => {
  const { activeWorkspace } = useWorkspaceStore();
  const navigate = useNavigate();
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [actionItemCount, setActionItemCount] = useState<number>(0);
  const [loading, setLoading] = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);

  // Soft delete state
  const [selectedMeeting, setSelectedMeeting] = useState<Meeting | null>(null);
  const [isTrashModalOpen, setIsTrashModalOpen] = useState(false);
  const [trashLoading, setTrashLoading] = useState(false);

  const fetchDashboardData = async () => {
    if (!activeWorkspace) {
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const [meetingsData, metricsData] = await Promise.allSettled([
        meetingsApi.getMeetings({ workspace_id: activeWorkspace.id }),
        intelligenceApi.getActionItemMetrics(activeWorkspace.id),
      ]);

      if (meetingsData.status === 'fulfilled') {
        setMeetings(Array.isArray(meetingsData.value) ? meetingsData.value : []);
      } else {
        setMeetings([]);
      }

      if (metricsData.status === 'fulfilled') {
        setActionItemCount(metricsData.value.total || 0);
      } else {
        setActionItemCount(0);
      }
    } catch (err) {
      console.error('Failed to load dashboard meetings', err);
      setMeetings([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboardData();
  }, [activeWorkspace]);

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
      fetchDashboardData();
    } catch (err: any) {
      alert(getErrorMessage(err));
    } finally {
      setTrashLoading(false);
    }
  };

  const safeMeetings = Array.isArray(meetings) ? meetings : [];
  const totalMeetings = safeMeetings.length;
  const completedMeetings = safeMeetings.filter((m) => m.status === 'COMPLETED').length;
  const totalDurationSeconds = safeMeetings.reduce((acc, m) => acc + (m.duration_seconds || 0), 0);
  const totalHoursTranscribed = (totalDurationSeconds / 3600).toFixed(1);

  return (
    <div className="space-y-8 animate-fade-in text-[#F8FAFC]">
      <CreateMeetingModal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} />

      <MoveToTrashModal
        isOpen={isTrashModalOpen}
        meetingTitle={selectedMeeting?.title}
        isLoading={trashLoading}
        onClose={() => setIsTrashModalOpen(false)}
        onConfirm={handleConfirmMoveToTrash}
      />

      {/* Hero Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-5 bg-[#102C4D] p-6 sm:p-7 rounded-2xl border border-[#1D4E78] shadow-xl bg-gradient-to-r from-[#102C4D] via-[#123456] to-[#102C4D]">
        <div>
          <h1 className="text-[26px] sm:text-[30px] font-bold text-[#F8FAFC] tracking-tight">
            {activeWorkspace ? activeWorkspace.name : 'Dashboard'}
          </h1>
          <p className="text-[14px] sm:text-[15px] text-[#B8C7DA] mt-1.5 max-w-2xl leading-relaxed">
            Turn your meeting recordings into actionable tasks, summaries, and vector-searchable knowledge.
          </p>
        </div>
        <div className="shrink-0">
          <Button onClick={() => setIsModalOpen(true)} icon={<Plus />}>
            Upload / New Meeting
          </Button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        <Card hover className="flex items-center space-x-4 bg-[#102C4D] border border-[#1D4E78]">
          <div className="p-3.5 rounded-xl bg-[#2563EB]/20 text-[#3B82F6] border border-[#2563EB]/40 shrink-0">
            <Video className="w-6 h-6" />
          </div>
          <div>
            <p className="text-[13px] sm:text-[14px] text-[#B8C7DA] font-medium">Total Meetings</p>
            <h3 className="text-[28px] sm:text-[30px] font-extrabold text-[#F8FAFC] tracking-tight mt-0.5">
              {loading ? '-' : totalMeetings}
            </h3>
          </div>
        </Card>

        <Card hover className="flex items-center space-x-4 bg-[#102C4D] border border-[#1D4E78]">
          <div className="p-3.5 rounded-xl bg-[#6366F1]/20 text-[#818CF8] border border-[#6366F1]/40 shrink-0">
            <Sparkles className="w-6 h-6" />
          </div>
          <div>
            <p className="text-[13px] sm:text-[14px] text-[#B8C7DA] font-medium">AI Intelligence Ready</p>
            <h3 className="text-[28px] sm:text-[30px] font-extrabold text-[#F8FAFC] tracking-tight mt-0.5">
              {loading ? '-' : completedMeetings}
            </h3>
          </div>
        </Card>

        <Card hover className="flex items-center space-x-4 bg-[#102C4D] border border-[#1D4E78]">
          <div className="p-3.5 rounded-xl bg-[#22C55E]/15 text-[#22C55E] border border-[#22C55E]/30 shrink-0">
            <CheckSquare className="w-6 h-6" />
          </div>
          <div>
            <p className="text-[13px] sm:text-[14px] text-[#B8C7DA] font-medium">Action Items</p>
            <h3 className="text-[28px] sm:text-[30px] font-extrabold text-[#F8FAFC] tracking-tight mt-0.5">
              {loading ? '-' : actionItemCount}
            </h3>
          </div>
        </Card>

        <Card hover className="flex items-center space-x-4 bg-[#102C4D] border border-[#1D4E78]">
          <div className="p-3.5 rounded-xl bg-[#F59E0B]/15 text-[#F59E0B] border border-[#F59E0B]/30 shrink-0">
            <Clock className="w-6 h-6" />
          </div>
          <div>
            <p className="text-[13px] sm:text-[14px] text-[#B8C7DA] font-medium">Hours Transcribed</p>
            <h3 className="text-[28px] sm:text-[30px] font-extrabold text-[#F8FAFC] tracking-tight mt-0.5">
              {loading ? '-' : `${totalHoursTranscribed} hrs`}
            </h3>
          </div>
        </Card>
      </div>

      {/* Recent Meetings Grid */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-[18px] sm:text-[20px] font-bold text-[#F8FAFC]">Recent Meetings</h2>
          <button
            onClick={() => navigate('/meetings')}
            className="text-[14px] text-[#3B82F6] hover:text-blue-300 flex items-center space-x-1 font-semibold transition-colors"
          >
            <span>View All</span>
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>

        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            <Skeleton className="h-44" />
            <Skeleton className="h-44" />
            <Skeleton className="h-44" />
          </div>
        ) : safeMeetings.length === 0 ? (
          <Card className="p-12 text-center text-[#8FA4BD] space-y-3 bg-[#102C4D] border border-[#1D4E78]">
            <Video className="w-10 h-10 text-[#8FA4BD] mx-auto" />
            <p className="text-[15px] font-semibold text-[#F8FAFC]">No meetings found in this workspace</p>
            <p className="text-[13px] text-[#8FA4BD]">Create or upload your first meeting recording to get started.</p>
            <div className="pt-2">
              <Button onClick={() => setIsModalOpen(true)} icon={<Plus />}>
                Create Meeting
              </Button>
            </div>
          </Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {safeMeetings.slice(0, 6).map((meeting) => (
              <MeetingCard
                key={meeting.id}
                meeting={meeting}
                onMoveToTrash={handleOpenTrashModal}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
