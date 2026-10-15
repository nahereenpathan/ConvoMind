import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Video, Upload, ArrowRight } from 'lucide-react';
import { Modal } from '../ui/Modal';
import { Button } from '../ui/Button';
import { useWorkspaceStore } from '../../stores/useWorkspaceStore';
import { meetingsApi } from '../../api/meetings';
import { getErrorMessage } from '../../utils/error';

interface CreateMeetingModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const CreateMeetingModal: React.FC<CreateMeetingModalProps> = ({ isOpen, onClose }) => {
  const { activeWorkspace } = useWorkspaceStore();
  const navigate = useNavigate();
  const [nativeTitle, setNativeTitle] = useState('');
  const [uploadTitle, setUploadTitle] = useState('');
  const [activeTab, setActiveTab] = useState<'native' | 'upload'>('native');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleStartNativeMeeting = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeWorkspace) return;
    setLoading(true);
    setError(null);

    const titleToUse = nativeTitle.trim() || `ConvoMind Meeting (${new Date().toLocaleDateString()})`;

    try {
      const meeting = await meetingsApi.createMeeting({
        title: titleToUse,
        workspace_id: activeWorkspace.id,
      });
      await meetingsApi.initNativeRoom(meeting.id);
      onClose();
      navigate(`/meetings/${meeting.id}/live`);
    } catch (err: any) {
      setError(getErrorMessage(err));
      setLoading(false);
    }
  };

  const handleStartUploadFlow = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeWorkspace) return;
    onClose();
    const titleParam = encodeURIComponent(uploadTitle.trim());
    navigate(`/meetings/new?mode=upload${titleParam ? `&title=${titleParam}` : ''}`);
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Create New Meeting"
      description="Choose how you want to create your meeting."
      maxWidth="2xl"
    >
      <div className="space-y-5 py-1">
        {error && (
          <div className="text-[13px] text-[#EF4444] bg-[#EF4444]/15 p-3 rounded-lg border border-[#EF4444]/40 font-medium">
            {error}
          </div>
        )}

        {/* Tab Selection Switcher */}
        <div className="grid grid-cols-2 p-1 bg-[#0A1B35] rounded-xl border border-[#1D4E78]">
          <button
            type="button"
            onClick={() => setActiveTab('native')}
            className={`py-2 px-3 rounded-lg text-[14px] font-bold transition-all flex items-center justify-center space-x-2 ${
              activeTab === 'native'
                ? 'bg-[#2563EB] text-white shadow-md'
                : 'text-[#8FA4BD] hover:text-[#F8FAFC]'
            }`}
          >
            <Video className="w-4 h-4" />
            <span>🎥 ConvoMind Meeting</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab('upload')}
            className={`py-2 px-3 rounded-lg text-[14px] font-bold transition-all flex items-center justify-center space-x-2 ${
              activeTab === 'upload'
                ? 'bg-[#6366F1] text-white shadow-md'
                : 'text-[#8FA4BD] hover:text-[#F8FAFC]'
            }`}
          >
            <Upload className="w-4 h-4" />
            <span>📁 Upload Recording</span>
          </button>
        </div>

        {activeTab === 'native' ? (
          <form onSubmit={handleStartNativeMeeting} className="p-5 bg-[#123456] border border-[#3B82F6]/50 rounded-2xl space-y-4 shadow-xl">
            <div className="flex items-center space-x-3">
              <div className="w-10 h-10 rounded-xl bg-[#2563EB]/20 border border-[#2563EB]/40 flex items-center justify-center text-[#3B82F6] shrink-0">
                <Video className="w-5 h-5" />
              </div>
              <div>
                <h4 className="text-[17px] font-bold text-[#F8FAFC]">🎥 ConvoMind Meeting</h4>
                <p className="text-[13px] text-[#B8C7DA]">Start a live video meeting directly inside ConvoMind with AI intelligence.</p>
              </div>
            </div>

            <div className="space-y-1.5 pt-2">
              <label className="block text-[13px] font-semibold text-[#B8C7DA]">Meeting Title</label>
              <input
                type="text"
                value={nativeTitle}
                onChange={(e) => setNativeTitle(e.target.value)}
                placeholder="e.g. Live Engineering Sync & Design Review"
                className="w-full bg-[#0A1B35] border border-[#1D4E78] rounded-lg p-3 text-[14px] text-[#F8FAFC] placeholder-[#8FA4BD] focus:outline-none focus:border-[#3B82F6]"
              />
            </div>

            <Button
              type="submit"
              isLoading={loading}
              className="w-full"
              icon={<ArrowRight className="w-4 h-4" />}
            >
              Start ConvoMind Meeting
            </Button>
          </form>
        ) : (
          <form onSubmit={handleStartUploadFlow} className="p-5 bg-[#123456] border border-[#818CF8]/50 rounded-2xl space-y-4 shadow-xl">
            <div className="flex items-center space-x-3">
              <div className="w-10 h-10 rounded-xl bg-[#6366F1]/20 border border-[#6366F1]/40 flex items-center justify-center text-[#818CF8] shrink-0">
                <Upload className="w-5 h-5" />
              </div>
              <div>
                <h4 className="text-[17px] font-bold text-[#F8FAFC]">📁 Upload Recording</h4>
                <p className="text-[13px] text-[#B8C7DA]">Upload an existing Zoom, Google Meet, Teams, or MP4 recording.</p>
              </div>
            </div>

            <div className="space-y-1.5 pt-2">
              <label className="block text-[13px] font-semibold text-[#B8C7DA]">Meeting Title</label>
              <input
                type="text"
                value={uploadTitle}
                onChange={(e) => setUploadTitle(e.target.value)}
                placeholder="e.g. Q3 Roadmap Review Recording"
                className="w-full bg-[#0A1B35] border border-[#1D4E78] rounded-lg p-3 text-[14px] text-[#F8FAFC] placeholder-[#8FA4BD] focus:outline-none focus:border-[#818CF8]"
              />
            </div>

            <Button
              type="submit"
              variant="outline"
              className="w-full"
              icon={<ArrowRight className="w-4 h-4" />}
            >
              Proceed to Upload
            </Button>
          </form>
        )}
      </div>
    </Modal>
  );
};
