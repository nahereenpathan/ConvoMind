import React, { useState } from 'react';
import { User, Check, Edit2 } from 'lucide-react';
import { SpeakerMap } from '../../types';
import { Modal } from '../ui/Modal';
import { Button } from '../ui/Button';
import { speakersApi } from '../../api/speakers';

interface SpeakerMappingModalProps {
  meetingId: string;
  isOpen: boolean;
  onClose: () => void;
  speakers: SpeakerMap[];
  onSpeakersUpdated: () => void;
}

export const SpeakerMappingModal: React.FC<SpeakerMappingModalProps> = ({
  meetingId,
  isOpen,
  onClose,
  speakers,
  onSpeakersUpdated,
}) => {
  const [editingLabel, setEditingLabel] = useState<string | null>(null);
  const [newName, setNewName] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSaveName = async (speakerLabel: string, speakerId?: string) => {
    if (!newName.trim() || saving) return;
    setSaving(true);
    setError(null);
    try {
      await speakersApi.updateSpeakerName(meetingId, speakerLabel, newName.trim(), speakerId);
      setEditingLabel(null);
      setNewName('');
      onSpeakersUpdated();
    } catch (err) {
      console.error('Failed to update speaker name', err);
      setError('Unable to update speaker name. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Map Diarized Speakers"
      description="Rename raw speaker labels (e.g. SPEAKER_00) to actual participant names across all transcript segments."
    >
      <div className="space-y-3 text-[#F8FAFC]">
        {error && (
          <div className="p-3 bg-[#EF4444]/15 border border-[#EF4444]/40 text-[13px] sm:text-[14px] text-[#EF4444] rounded-lg font-medium">
            {error}
          </div>
        )}

        {speakers.length === 0 ? (
          <p className="text-[13px] sm:text-[14px] text-[#8FA4BD]">No speakers identified yet. Run diarization first.</p>
        ) : (
          speakers.map((spk) => (
            <div
              key={spk.speaker_label || spk.id}
              className="flex items-center justify-between p-3.5 rounded-xl bg-[#123456] border border-[#1D4E78]"
            >
              <div className="flex items-center space-x-3">
                <div className="p-2 rounded-lg bg-[#2563EB]/20 text-[#3B82F6] border border-[#2563EB]/40">
                  <User className="w-4 h-4" />
                </div>
                <div>
                  <span className="text-[12px] font-mono text-[#8FA4BD] block">{spk.speaker_label}</span>
                  {editingLabel === spk.speaker_label ? (
                    <div className="flex items-center space-x-2 mt-1">
                      <input
                        type="text"
                        value={newName}
                        onChange={(e) => setNewName(e.target.value)}
                        placeholder="e.g. Alice Smith"
                        className="bg-[#102C4D] border border-[#1D4E78] text-[#F8FAFC] text-[13px] sm:text-[14px] rounded px-2.5 py-1 focus:outline-none focus:border-[#3B82F6]"
                        autoFocus
                      />
                      <button
                        onClick={() => handleSaveName(spk.speaker_label, spk.id)}
                        disabled={saving}
                        className="p-1.5 bg-[#2563EB] hover:bg-[#3B82F6] disabled:opacity-50 text-white rounded transition-colors"
                      >
                        <Check className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  ) : (
                    <span className="text-[14px] sm:text-[15px] font-semibold text-[#F8FAFC] block">
                      {spk.display_name || spk.speaker_label}
                    </span>
                  )}
                </div>
              </div>

              {editingLabel !== spk.speaker_label && (
                <button
                  onClick={() => {
                    setEditingLabel(spk.speaker_label);
                    setNewName(spk.display_name || '');
                  }}
                  className="p-1.5 text-[#8FA4BD] hover:text-[#F8FAFC] hover:bg-[#1D4E78] rounded transition-colors"
                >
                  <Edit2 className="w-4 h-4" />
                </button>
              )}
            </div>
          ))
        )}
      </div>

      <div className="flex justify-end pt-4">
        <Button variant="outline" onClick={onClose}>
          Done
        </Button>
      </div>
    </Modal>
  );
};
