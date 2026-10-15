import React, { useEffect, useState } from 'react';
import { Camera, Mic, Volume2, Check, Play } from 'lucide-react';
import { Modal } from '../ui/Modal';
import { Button } from '../ui/Button';
import { MediaDeviceOption } from '../../types';
import { mediaService } from '../../services/mediaService';

interface DeviceSettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  localIdentity?: string;
  onSwitchCamera?: (deviceId: string) => Promise<void>;
  onSwitchMicrophone?: (deviceId: string) => Promise<void>;
}

export const DeviceSettingsModal: React.FC<DeviceSettingsModalProps> = ({
  isOpen,
  onClose,
  localIdentity,
}) => {
  const [cameras, setCameras] = useState<MediaDeviceOption[]>([]);
  const [microphones, setMicrophones] = useState<MediaDeviceOption[]>([]);
  const [speakers, setSpeakers] = useState<MediaDeviceOption[]>([]);

  const [selectedCamera, setSelectedCamera] = useState<string>('');
  const [selectedMic, setSelectedMic] = useState<string>('');
  const [selectedSpeaker, setSelectedSpeaker] = useState<string>('');

  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!isOpen) return;

    const loadDevices = async () => {
      const dev = await mediaService.getAvailableDevices();
      setCameras(dev.cameras);
      setMicrophones(dev.microphones);
      setSpeakers(dev.speakers);

      if (dev.cameras.length > 0) setSelectedCamera(dev.cameras[0].deviceId);
      if (dev.microphones.length > 0) setSelectedMic(dev.microphones[0].deviceId);
      if (dev.speakers.length > 0) setSelectedSpeaker(dev.speakers[0].deviceId);
    };

    loadDevices();
  }, [isOpen]);

  const [isPlayingTestSound, setIsPlayingTestSound] = useState(false);

  const handleApplySettings = async () => {
    if (selectedCamera) {
      await mediaService.switchCamera(selectedCamera, localIdentity);
    }
    if (selectedMic) {
      await mediaService.switchMicrophone(selectedMic, localIdentity);
    }
    if (selectedSpeaker) {
      await mediaService.switchSpeaker(selectedSpeaker);
    }
    setSaved(true);
    setTimeout(() => {
      setSaved(false);
      onClose();
    }, 1000);
  };

  const handleTestSpeaker = async () => {
    setIsPlayingTestSound(true);
    await mediaService.playTestSound(selectedSpeaker);
    setTimeout(() => {
      setIsPlayingTestSound(false);
    }, 700);
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Meeting Media Settings"
      description="Choose audio and video devices for your live meeting."
      maxWidth="md"
    >
      <div className="space-y-5 py-2 text-[#F8FAFC]">
        {/* Camera Selector */}
        <div className="space-y-2">
          <label className="flex items-center space-x-2 text-[14px] font-semibold text-[#B8C7DA]">
            <Camera className="w-4 h-4 text-[#3B82F6]" />
            <span>Camera Input</span>
          </label>
          <select
            value={selectedCamera}
            onChange={(e) => setSelectedCamera(e.target.value)}
            className="w-full bg-[#123456] border border-[#1D4E78] text-[#F8FAFC] text-[14px] rounded-lg p-3 focus:outline-none focus:border-[#3B82F6]"
          >
            {cameras.length === 0 ? (
              <option value="">Default Camera</option>
            ) : (
              cameras.map((c) => (
                <option key={c.deviceId} value={c.deviceId}>
                  {c.label}
                </option>
              ))
            )}
          </select>
        </div>

        {/* Microphone Selector */}
        <div className="space-y-2">
          <label className="flex items-center space-x-2 text-[14px] font-semibold text-[#B8C7DA]">
            <Mic className="w-4 h-4 text-[#22C55E]" />
            <span>Microphone Input</span>
          </label>
          <select
            value={selectedMic}
            onChange={(e) => setSelectedMic(e.target.value)}
            className="w-full bg-[#123456] border border-[#1D4E78] text-[#F8FAFC] text-[14px] rounded-lg p-3 focus:outline-none focus:border-[#3B82F6]"
          >
            {microphones.length === 0 ? (
              <option value="">Default Microphone</option>
            ) : (
              microphones.map((m) => (
                <option key={m.deviceId} value={m.deviceId}>
                  {m.label}
                </option>
              ))
            )}
          </select>
        </div>

        {/* Speaker Output Selector */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <label className="flex items-center space-x-2 text-[14px] font-semibold text-[#B8C7DA]">
              <Volume2 className="w-4 h-4 text-[#818CF8]" />
              <span>Audio Output (Speakers)</span>
            </label>
            <button
              type="button"
              onClick={handleTestSpeaker}
              disabled={isPlayingTestSound}
              className="text-[12px] text-[#3B82F6] hover:text-[#60A5FA] font-bold flex items-center space-x-1 transition-colors"
            >
              <Play className={`w-3.5 h-3.5 ${isPlayingTestSound ? 'animate-spin' : ''}`} />
              <span>{isPlayingTestSound ? 'Playing...' : 'Test Speaker'}</span>
            </button>
          </div>
          <select
            value={selectedSpeaker}
            onChange={(e) => setSelectedSpeaker(e.target.value)}
            className="w-full bg-[#123456] border border-[#1D4E78] text-[#F8FAFC] text-[14px] rounded-lg p-3 focus:outline-none focus:border-[#3B82F6]"
          >
            {speakers.length === 0 ? (
              <option value="">Default Speaker System</option>
            ) : (
              speakers.map((s) => (
                <option key={s.deviceId} value={s.deviceId}>
                  {s.label}
                </option>
              ))
            )}
          </select>
        </div>

        <div className="pt-4 flex items-center justify-end space-x-3 border-t border-[#1D4E78]">
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={handleApplySettings} icon={saved ? <Check className="text-[#22C55E]" /> : undefined}>
            {saved ? 'Settings Saved' : 'Apply Device Settings'}
          </Button>
        </div>
      </div>
    </Modal>
  );
};
