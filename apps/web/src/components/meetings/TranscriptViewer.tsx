import React, { useState } from 'react';
import { Search, Copy, Check, Users, Edit3, Save, AlertTriangle } from 'lucide-react';
import { TranscriptSegment, SpeakerMap } from '../../types';
import { Input } from '../ui/Input';
import { Button } from '../ui/Button';
import { transcriptsApi } from '../../api/transcripts';

interface TranscriptViewerProps {
  meetingId: string;
  segments: TranscriptSegment[];
  speakers?: SpeakerMap[];
  status?: string;
  errorMessage?: string;
  onOpenSpeakerModal?: () => void;
  onRefresh?: () => void;
}

export const TranscriptViewer: React.FC<TranscriptViewerProps> = ({
  meetingId,
  segments,
  speakers = [],
  status,
  errorMessage,
  onOpenSpeakerModal,
  onRefresh,
}) => {
  const [search, setSearch] = useState('');
  const [copied, setCopied] = useState(false);
  const [editingSegmentId, setEditingSegmentId] = useState<string | null>(null);
  const [editText, setEditText] = useState('');
  const [saving, setSaving] = useState(false);

  const getSpeakerDisplayName = (label?: string) => {
    if (!label) return 'Speaker';
    if (speakers && speakers.length > 0) {
      const match = speakers.find((s) => s.speaker_label === label);
      if (match && match.display_name) {
        return match.display_name;
      }
    }
    return label;
  };

  const filteredSegments = segments.filter((seg) => {
    const displayName = getSpeakerDisplayName(seg.speaker_label).toLowerCase();
    const rawLabel = (seg.speaker_label || '').toLowerCase();
    const query = search.toLowerCase();
    return (
      seg.text.toLowerCase().includes(query) ||
      rawLabel.includes(query) ||
      displayName.includes(query)
    );
  });

  const formatTimestamp = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const handleCopy = () => {
    const fullText = segments
      .map((seg) => `[${formatTimestamp(seg.start_time)}] ${getSpeakerDisplayName(seg.speaker_label)}: ${seg.text}`)
      .join('\n');
    navigator.clipboard.writeText(fullText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleSaveSegment = async (id: string) => {
    setSaving(true);
    try {
      await transcriptsApi.updateSegment(meetingId, id, editText);
      setEditingSegmentId(null);
      if (onRefresh) onRefresh();
    } catch (err) {
      console.error('Failed to update segment', err);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-4">
      {(status === 'FAILED' || errorMessage) && (
        <div className="p-4 rounded-xl bg-[#EF4444]/15 border border-[#EF4444]/40 text-[#EF4444] space-y-1">
          <div className="flex items-center space-x-2.5 font-semibold text-[15px]">
            <AlertTriangle className="w-5 h-5 shrink-0 text-[#EF4444]" />
            <span>Transcription unavailable / provider not configured</span>
          </div>
          {errorMessage && (
            <p className="text-[13px] text-[#B8C7DA] pl-7 leading-relaxed">{errorMessage}</p>
          )}
        </div>
      )}

      <div className="flex flex-col sm:flex-row items-center justify-between gap-3">
        <div className="w-full sm:w-72">
          <Input
            placeholder="Search transcript..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            icon={<Search className="w-4 h-4 text-[#8FA4BD]" />}
          />
        </div>

        <div className="flex items-center space-x-2 w-full sm:w-auto justify-end">
          {onOpenSpeakerModal && (
            <Button variant="outline" size="sm" onClick={onOpenSpeakerModal} icon={<Users />}>
              Map Speakers
            </Button>
          )}
          <Button variant="secondary" size="sm" onClick={handleCopy} icon={copied ? <Check /> : <Copy />}>
            {copied ? 'Copied' : 'Copy All'}
          </Button>
        </div>
      </div>

      <div className="space-y-3 max-h-[600px] overflow-y-auto custom-scrollbar pr-2">
        {filteredSegments.length === 0 ? (
          <div className="p-12 text-center text-[#8FA4BD] text-[14px]">
            {segments.length === 0 ? 'No transcript available yet.' : 'No matching segments found.'}
          </div>
        ) : (
          filteredSegments.map((seg) => (
            <div
              key={seg.id}
              className="p-4 sm:p-4.5 rounded-xl bg-[#102C4D] border border-[#1D4E78] hover:bg-[#123456] hover:border-[#3B82F6] transition-all space-y-2.5 group"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  <span className="font-semibold text-[#3B82F6] bg-[#2563EB]/20 px-2.5 py-0.5 rounded text-[13px] sm:text-[14px] border border-[#2563EB]/40">
                    {getSpeakerDisplayName(seg.speaker_label)}
                  </span>
                  <span className="text-[#8FA4BD] font-mono text-[13px] sm:text-[14px]">
                    [{formatTimestamp(seg.start_time)} - {formatTimestamp(seg.end_time)}]
                  </span>
                </div>

                {editingSegmentId !== seg.id && (
                  <button
                    onClick={() => {
                      setEditingSegmentId(seg.id);
                      setEditText(seg.text);
                    }}
                    className="opacity-0 group-hover:opacity-100 transition-opacity p-1 text-[#8FA4BD] hover:text-[#F8FAFC]"
                  >
                    <Edit3 className="w-4 h-4" />
                  </button>
                )}
              </div>

              {editingSegmentId === seg.id ? (
                <div className="space-y-2.5 mt-2">
                  <textarea
                    value={editText}
                    onChange={(e) => setEditText(e.target.value)}
                    className="w-full bg-[#123456] border border-[#1D4E78] rounded-lg p-3 text-[15px] sm:text-[16px] leading-[1.6] text-[#F8FAFC] focus:outline-none focus:border-[#3B82F6]"
                    rows={3}
                  />
                  <div className="flex justify-end space-x-2">
                    <Button variant="ghost" size="sm" onClick={() => setEditingSegmentId(null)}>
                      Cancel
                    </Button>
                    <Button
                      size="sm"
                      isLoading={saving}
                      onClick={() => handleSaveSegment(seg.id)}
                      icon={<Save />}
                    >
                      Save
                    </Button>
                  </div>
                </div>
              ) : (
                <p className="text-[15px] sm:text-[16px] leading-[1.6] text-[#F8FAFC] font-normal">{seg.text}</p>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
};
