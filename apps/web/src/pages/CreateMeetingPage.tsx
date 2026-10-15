import React, { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { ArrowLeft, Sparkles, Video, Upload, ArrowRight, CheckCircle } from 'lucide-react';
import { useWorkspaceStore } from '../stores/useWorkspaceStore';
import { meetingsApi } from '../api/meetings';
import { RecordingUploader } from '../components/meetings/RecordingUploader';
import { Input } from '../components/ui/Input';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { getErrorMessage } from '../utils/error';

export const CreateMeetingPage: React.FC = () => {
  const { activeWorkspace } = useWorkspaceStore();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  // Native Meeting Form State
  const [nativeTitle, setNativeTitle] = useState('');
  const [nativeDescription, setNativeDescription] = useState('');
  const [nativeLoading, setNativeLoading] = useState(false);

  // Upload Form State
  const [uploadTitle, setUploadTitle] = useState(searchParams.get('title') || '');
  const [uploadDescription, setUploadDescription] = useState('');
  const [uploadLoading, setUploadLoading] = useState(false);

  const [createdMeetingId, setCreatedMeetingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleStartNativeMeeting = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeWorkspace) return;
    setNativeLoading(true);
    setError(null);

    const titleToUse = nativeTitle.trim() || `ConvoMind Meeting (${new Date().toLocaleDateString()})`;

    try {
      const meeting = await meetingsApi.createMeeting({
        title: titleToUse,
        description: nativeDescription.trim() || undefined,
        workspace_id: activeWorkspace.id,
      });
      await meetingsApi.initNativeRoom(meeting.id);
      navigate(`/meetings/${meeting.id}/live`);
    } catch (err: any) {
      setError(getErrorMessage(err));
      setNativeLoading(false);
    }
  };

  const handleCreateUploadMetadata = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeWorkspace) return;
    setUploadLoading(true);
    setError(null);

    const titleToUse = uploadTitle.trim() || `Uploaded Recording (${new Date().toLocaleDateString()})`;

    try {
      const meeting = await meetingsApi.createMeeting({
        title: titleToUse,
        description: uploadDescription.trim() || undefined,
        workspace_id: activeWorkspace.id,
      });
      setCreatedMeetingId(meeting.id);
    } catch (err: any) {
      setError(getErrorMessage(err));
    } finally {
      setUploadLoading(false);
    }
  };

  return (
    <div className="max-w-5xl mx-auto space-y-6 animate-fade-in text-[#F8FAFC]">
      <button
        onClick={() => navigate('/meetings')}
        className="flex items-center space-x-2 text-[13px] sm:text-[14px] font-semibold text-[#8FA4BD] hover:text-[#F8FAFC] transition-colors"
      >
        <ArrowLeft className="w-4 h-4" />
        <span>Back to Meetings</span>
      </button>

      <div>
        <h1 className="text-[26px] sm:text-[30px] font-bold text-[#F8FAFC]">Create New Meeting</h1>
        <p className="text-[14px] sm:text-[15px] text-[#B8C7DA] mt-1">
          Choose how you want to create your meeting inside ConvoMind.
        </p>
      </div>

      {error && (
        <div className="text-[14px] text-[#EF4444] bg-[#EF4444]/15 p-4 rounded-xl border border-[#EF4444]/40 font-medium">
          {error}
        </div>
      )}

      {!createdMeetingId ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* SECTION 1: NATIVE CONVOMIND MEETING */}
          <Card className="flex flex-col justify-between bg-[#102C4D] border border-[#1D4E78] hover:border-[#3B82F6]/60 p-6 sm:p-7 shadow-xl space-y-6">
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="w-12 h-12 rounded-xl bg-[#2563EB]/20 border border-[#2563EB]/40 flex items-center justify-center text-[#3B82F6] shadow-md">
                  <Video className="w-6 h-6" />
                </div>
                <span className="inline-flex items-center space-x-1 text-[11px] font-bold text-[#3B82F6] bg-[#2563EB]/15 border border-[#2563EB]/30 px-3 py-1 rounded-full">
                  <Sparkles className="w-3 h-3" />
                  <span>Native Video</span>
                </span>
              </div>

              <div>
                <h3 className="text-[20px] font-bold text-[#F8FAFC]">🎥 ConvoMind Meeting</h3>
                <p className="text-[14px] text-[#B8C7DA] mt-1 leading-relaxed">
                  Start a live meeting directly inside ConvoMind with video, audio, screen sharing, chat and AI meeting intelligence.
                </p>
              </div>

              <form onSubmit={handleStartNativeMeeting} id="native-meeting-form" className="space-y-4 pt-2">
                <Input
                  label="Meeting Title"
                  placeholder="e.g. Sprint Review & Live Architecture Sync"
                  value={nativeTitle}
                  onChange={(e) => setNativeTitle(e.target.value)}
                />

                <div className="space-y-1.5">
                  <label className="block text-[13px] font-semibold text-[#B8C7DA]">Agenda / Description (Optional)</label>
                  <textarea
                    value={nativeDescription}
                    onChange={(e) => setNativeDescription(e.target.value)}
                    placeholder="Briefly state key discussion points..."
                    rows={2}
                    className="w-full bg-[#123456] border border-[#1D4E78] rounded-lg p-3 text-[14px] text-[#F8FAFC] placeholder-[#8FA4BD] focus:outline-none focus:border-[#3B82F6]"
                  />
                </div>
              </form>
            </div>

            <div className="pt-4 border-t border-[#1D4E78]">
              <Button
                type="submit"
                form="native-meeting-form"
                isLoading={nativeLoading}
                className="w-full py-3"
                icon={<ArrowRight className="w-4 h-4" />}
              >
                Start ConvoMind Meeting
              </Button>
            </div>
          </Card>

          {/* SECTION 2: UPLOAD MEETING RECORDING */}
          <Card className="flex flex-col justify-between bg-[#102C4D] border border-[#1D4E78] hover:border-[#818CF8]/60 p-6 sm:p-7 shadow-xl space-y-6">
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="w-12 h-12 rounded-xl bg-[#6366F1]/20 border border-[#6366F1]/40 flex items-center justify-center text-[#818CF8] shadow-md">
                  <Upload className="w-6 h-6" />
                </div>
                <span className="inline-flex items-center text-[11px] font-bold text-[#818CF8] bg-[#6366F1]/15 border border-[#6366F1]/30 px-3 py-1 rounded-full">
                  Whisper AI Analysis
                </span>
              </div>

              <div>
                <h3 className="text-[20px] font-bold text-[#F8FAFC]">📁 Upload Meeting Recording</h3>
                <p className="text-[14px] text-[#B8C7DA] mt-1 leading-relaxed">
                  Upload a recording from Zoom, Google Meet, Microsoft Teams or another platform for automated processing.
                </p>
              </div>

              <form onSubmit={handleCreateUploadMetadata} id="upload-recording-form" className="space-y-4 pt-2">
                <Input
                  label="Meeting Title"
                  placeholder="e.g. Q3 Strategic Planning Session"
                  value={uploadTitle}
                  onChange={(e) => setUploadTitle(e.target.value)}
                />

                <div className="space-y-1.5">
                  <label className="block text-[13px] font-semibold text-[#B8C7DA]">Description / Notes (Optional)</label>
                  <textarea
                    value={uploadDescription}
                    onChange={(e) => setUploadDescription(e.target.value)}
                    placeholder="Context about the recorded video/audio..."
                    rows={2}
                    className="w-full bg-[#123456] border border-[#1D4E78] rounded-lg p-3 text-[14px] text-[#F8FAFC] placeholder-[#8FA4BD] focus:outline-none focus:border-[#818CF8]"
                  />
                </div>
              </form>
            </div>

            <div className="pt-4 border-t border-[#1D4E78]">
              <Button
                type="submit"
                form="upload-recording-form"
                variant="outline"
                isLoading={uploadLoading}
                className="w-full py-3"
                icon={<ArrowRight className="w-4 h-4" />}
              >
                Upload Recording
              </Button>
            </div>
          </Card>
        </div>
      ) : (
        <Card className="space-y-6 bg-[#102C4D] border border-[#1D4E78] p-7">
          <div className="flex items-center space-x-3 p-4 rounded-xl bg-[#2563EB]/20 border border-[#2563EB]/40">
            <CheckCircle className="w-5 h-5 text-[#3B82F6]" />
            <div>
              <h4 className="text-[16px] font-semibold text-[#F8FAFC]">Meeting metadata ready</h4>
              <p className="text-[13px] text-[#8FA4BD]">Proceed to select and upload your video/audio file below.</p>
            </div>
          </div>

          <RecordingUploader
            meetingId={createdMeetingId}
            onUploadComplete={() => navigate(`/meetings/${createdMeetingId}`)}
          />
        </Card>
      )}
    </div>
  );
};
