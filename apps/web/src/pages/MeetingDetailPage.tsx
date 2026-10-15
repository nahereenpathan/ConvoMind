import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  Sparkles,
  FileText,
  MessageSquare,
  Mail,
  Users,
  RefreshCw,
  Trash2,
  RotateCcw,
} from 'lucide-react';
import { meetingsApi } from '../api/meetings';
import { transcriptsApi } from '../api/transcripts';
import { intelligenceApi } from '../api/intelligence';
import { speakersApi } from '../api/speakers';
import { Meeting, TranscriptSegment, IntelligenceResult, SpeakerMap } from '../types';
import { Tabs } from '../components/ui/Tabs';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { Card } from '../components/ui/Card';
import { Skeleton } from '../components/ui/Skeleton';
import { IntelligenceView } from '../components/meetings/IntelligenceView';
import { TranscriptViewer } from '../components/meetings/TranscriptViewer';
import { ChatContainer } from '../components/meetings/ChatContainer';
import { SpeakerMappingModal } from '../components/meetings/SpeakerMappingModal';
import { FollowUpModal } from '../components/meetings/FollowUpModal';
import { RecordingUploader } from '../components/meetings/RecordingUploader';
import { MoveToTrashModal } from '../components/meetings/MoveToTrashModal';
import { RestoreModal } from '../components/meetings/RestoreModal';
import { PermanentDeleteModal } from '../components/meetings/PermanentDeleteModal';
import { getErrorMessage } from '../utils/error';

export const MeetingDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [meeting, setMeeting] = useState<Meeting | null>(null);
  const [segments, setSegments] = useState<TranscriptSegment[]>([]);
  const [intelligence, setIntelligence] = useState<IntelligenceResult | null>(null);
  const [speakers, setSpeakers] = useState<SpeakerMap[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('intelligence');

  const [isSpeakerModalOpen, setIsSpeakerModalOpen] = useState(false);
  const [isFollowUpModalOpen, setIsFollowUpModalOpen] = useState(false);
  const [reprocessing, setReprocessing] = useState(false);

  // Soft delete & permanent delete modal states
  const [isTrashModalOpen, setIsTrashModalOpen] = useState(false);
  const [isRestoreModalOpen, setIsRestoreModalOpen] = useState(false);
  const [isPermanentDeleteModalOpen, setIsPermanentDeleteModalOpen] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);

  const [transcriptStatus, setTranscriptStatus] = useState<string | undefined>(undefined);
  const [transcriptErrorMessage, setTranscriptErrorMessage] = useState<string | undefined>(undefined);

  const fetchMeetingData = async (showLoading = true) => {
    if (!id) return;
    if (showLoading) setLoading(true);
    try {
      const meetingData = await meetingsApi.getMeeting(id);
      setMeeting(meetingData);

      const [transcriptRes, intelligenceRes, speakersRes] = await Promise.allSettled([
        transcriptsApi.getTranscriptFull(id),
        intelligenceApi.getIntelligence(id),
        speakersApi.getSpeakers(id),
      ]);

      if (transcriptRes.status === 'fulfilled') {
        const data = transcriptRes.value;
        if (data && 'segments' in data && Array.isArray(data.segments)) {
          setSegments(data.segments);
        } else if (Array.isArray(data)) {
          setSegments(data);
        }
        setTranscriptStatus(data?.status);
        setTranscriptErrorMessage(data?.error_message);
      }
      if (intelligenceRes.status === 'fulfilled') setIntelligence(intelligenceRes.value);
      if (speakersRes.status === 'fulfilled') setSpeakers(speakersRes.value);
    } catch (err) {
      console.error('Failed to load meeting details', err);
    } finally {
      if (showLoading) setLoading(false);
    }
  };

  useEffect(() => {
    // Reset state immediately when meeting ID changes to prevent cross-meeting UI leakage
    setMeeting(null);
    setSegments([]);
    setIntelligence(null);
    setSpeakers([]);
    setTranscriptStatus(undefined);
    setTranscriptErrorMessage(undefined);
    fetchMeetingData(true);
  }, [id]);

  // Real-time status polling while recording, transcribing, or AI processing
  useEffect(() => {
    const activeMeetingStatuses = ['RECORDING', 'PROCESSING', 'TRANSCRIBING', 'AI_PROCESSING', 'QUEUED', 'IN_PROGRESS'];
    const activeTranscriptStatuses = ['PROCESSING', 'QUEUED', 'PENDING', 'TRANSCRIBING'];

    const isMeetingActive = meeting && activeMeetingStatuses.includes(meeting.status);
    const isTranscriptActive = transcriptStatus && activeTranscriptStatuses.includes(transcriptStatus);

    if (!isMeetingActive && !isTranscriptActive) return;

    const interval = setInterval(() => {
      fetchMeetingData(false);
    }, 3000);

    return () => clearInterval(interval);
  }, [id, meeting?.status, transcriptStatus]);

  const handleProcessPipeline = async () => {
    if (!id) return;
    setReprocessing(true);
    try {
      await meetingsApi.processMeeting(id);
      await fetchMeetingData();
    } catch (err) {
      console.error('Failed to run pipeline', err);
    } finally {
      setReprocessing(false);
    }
  };

  const handleConfirmMoveToTrash = async () => {
    if (!id) return;
    setActionLoading(true);
    try {
      await meetingsApi.moveToTrash(id);
      setIsTrashModalOpen(false);
      navigate('/meetings');
    } catch (err: any) {
      alert(getErrorMessage(err));
    } finally {
      setActionLoading(false);
    }
  };

  const handleConfirmRestore = async () => {
    if (!id) return;
    setActionLoading(true);
    try {
      await meetingsApi.restoreMeeting(id);
      setIsRestoreModalOpen(false);
      fetchMeetingData();
    } catch (err: any) {
      alert(getErrorMessage(err));
    } finally {
      setActionLoading(false);
    }
  };

  const [modalError, setModalError] = useState<string | null>(null);

  const handleConfirmPermanentDelete = async () => {
    if (!id) return;
    setActionLoading(true);
    setModalError(null);
    try {
      await meetingsApi.permanentlyDeleteMeeting(id);
      setIsPermanentDeleteModalOpen(false);
      navigate('/trash');
    } catch (err: any) {
      setModalError('Unable to permanently delete this meeting. Please try again.');
    } finally {
      setActionLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-40" />
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-96 w-full" />
      </div>
    );
  }

  if (!meeting) {
    return (
      <div className="p-12 text-center text-[#7F94AF]">
        <p className="text-sm sm:text-base font-semibold text-[#F8FAFC]">Meeting not found.</p>
        <Button variant="ghost" className="mt-4" onClick={() => navigate('/meetings')}>
          Return to Meetings
        </Button>
      </div>
    );
  }

  const isTrashed = !!meeting.deleted_at;

  const tabs = [
    { id: 'intelligence', label: 'AI Intelligence', icon: <Sparkles /> },
    { id: 'transcript', label: 'Transcript', icon: <FileText />, badge: segments.length },
    { id: 'chat', label: 'AI RAG Chat', icon: <MessageSquare /> },
  ];

  return (
    <div className="space-y-6 animate-fade-in text-[#F8FAFC]">
      <button
        onClick={() => navigate(isTrashed ? '/trash' : '/meetings')}
        className="flex items-center space-x-2 text-[13px] sm:text-[14px] font-semibold text-[#8FA4BD] hover:text-[#F8FAFC] transition-colors"
      >
        <ArrowLeft className="w-4 h-4" />
        <span>Back to {isTrashed ? 'Trash' : 'Meetings'}</span>
      </button>

      {/* Trashed Alert Banner */}
      {isTrashed && (
        <div className="p-4 rounded-2xl bg-[#EF4444]/15 border border-[#EF4444]/40 text-[#EF4444] flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center space-x-3">
            <Trash2 className="w-5 h-5 shrink-0" />
            <div>
              <p className="font-bold text-[15px]">This meeting is in Trash.</p>
              <p className="text-[13px] text-[#B8C7DA]">It is hidden from active lists and dashboard statistics.</p>
            </div>
          </div>
          <div className="flex items-center space-x-3 shrink-0">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setIsRestoreModalOpen(true)}
              icon={<RotateCcw className="w-4 h-4 text-[#22C55E]" />}
            >
              Restore
            </Button>
            <Button
              variant="danger"
              size="sm"
              onClick={() => setIsPermanentDeleteModalOpen(true)}
              icon={<Trash2 className="w-4 h-4" />}
            >
              Delete Permanently
            </Button>
          </div>
        </div>
      )}

      {/* Header Banner */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-5 bg-[#102C4D] p-6 sm:p-7 rounded-2xl border border-[#1D4E78] shadow-xl bg-gradient-to-r from-[#102C4D] via-[#123456] to-[#102C4D]">
        <div className="space-y-1.5">
          <div className="flex items-center space-x-3">
            <h1 className="text-[26px] sm:text-[30px] font-bold text-[#F8FAFC] tracking-tight">{meeting.title}</h1>
            <Badge variant={meeting.status === 'COMPLETED' ? 'success' : 'warning'}>
              {meeting.status}
            </Badge>
          </div>
          {meeting.description && <p className="text-[14px] sm:text-[15px] text-[#B8C7DA] max-w-2xl leading-relaxed">{meeting.description}</p>}
        </div>

        <div className="flex flex-wrap items-center gap-2.5 shrink-0">
          {!isTrashed && (
            <>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setIsSpeakerModalOpen(true)}
                icon={<Users />}
              >
                Map Speakers
              </Button>

              <Button
                variant="secondary"
                size="sm"
                onClick={() => setIsFollowUpModalOpen(true)}
                icon={<Mail />}
              >
                Draft Follow-Up Email
              </Button>

              <Button
                size="sm"
                onClick={handleProcessPipeline}
                isLoading={reprocessing}
                icon={<RefreshCw />}
              >
                Re-run AI Pipeline
              </Button>

              <Button
                variant="danger"
                size="sm"
                onClick={() => setIsTrashModalOpen(true)}
                icon={<Trash2 className="w-4 h-4" />}
              >
                Move to Trash
              </Button>
            </>
          )}
        </div>
      </div>

      {meeting.status === 'SCHEDULED' && segments.length === 0 && (
        <Card className="p-6 bg-[#102C4D] border border-[#1D4E78]">
          <h3 className="text-[16px] sm:text-[18px] font-bold text-[#F8FAFC] mb-4">Attach Recording File</h3>
          <RecordingUploader meetingId={meeting.id} onUploadComplete={fetchMeetingData} />
        </Card>
      )}

      <div className="space-y-6">
        <Tabs tabs={tabs} activeTab={activeTab} onChange={setActiveTab} />

        {activeTab === 'intelligence' && (
          <IntelligenceView
            meetingId={meeting.id}
            intelligence={intelligence}
            onRefresh={fetchMeetingData}
          />
        )}

        {activeTab === 'transcript' && (
          <TranscriptViewer
            meetingId={meeting.id}
            segments={segments}
            speakers={speakers}
            status={transcriptStatus}
            errorMessage={transcriptErrorMessage}
            onOpenSpeakerModal={() => setIsSpeakerModalOpen(true)}
            onRefresh={fetchMeetingData}
          />
        )}

        {activeTab === 'chat' && <ChatContainer meetingId={meeting.id} />}
      </div>

      <SpeakerMappingModal
        meetingId={meeting.id}
        isOpen={isSpeakerModalOpen}
        onClose={() => setIsSpeakerModalOpen(false)}
        speakers={speakers}
        onSpeakersUpdated={fetchMeetingData}
      />

      <FollowUpModal
        meetingId={meeting.id}
        isOpen={isFollowUpModalOpen}
        onClose={() => setIsFollowUpModalOpen(false)}
      />

      <MoveToTrashModal
        isOpen={isTrashModalOpen}
        meetingTitle={meeting.title}
        isLoading={actionLoading}
        onClose={() => setIsTrashModalOpen(false)}
        onConfirm={handleConfirmMoveToTrash}
      />

      <RestoreModal
        isOpen={isRestoreModalOpen}
        meetingTitle={meeting.title}
        isLoading={actionLoading}
        onClose={() => setIsRestoreModalOpen(false)}
        onConfirm={handleConfirmRestore}
      />

      <PermanentDeleteModal
        isOpen={isPermanentDeleteModalOpen}
        meetingTitle={meeting.title}
        isLoading={actionLoading}
        errorMessage={modalError}
        onClose={() => {
          setIsPermanentDeleteModalOpen(false);
          setModalError(null);
        }}
        onConfirm={handleConfirmPermanentDelete}
      />
    </div>
  );
};
