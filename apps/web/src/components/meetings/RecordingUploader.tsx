import React, { useState, useRef } from 'react';
import { Upload, FileAudio, AlertCircle, Loader2, CheckCircle2, RotateCcw } from 'lucide-react';
import { meetingsApi } from '../../api/meetings';
import { Button } from '../ui/Button';
import { getErrorMessage } from '../../utils/error';
import { Recording } from '../../types';

interface RecordingUploaderProps {
  meetingId: string;
  onUploadComplete: () => void;
}

type PipelineStage = 'idle' | 'uploading' | 'processing' | 'completed' | 'failed';

const ALLOWED_EXTENSIONS = ['.mp3', '.wav', '.m4a', '.ogg', '.mp4', '.webm', '.mov'];

export const RecordingUploader: React.FC<RecordingUploaderProps> = ({
  meetingId,
  onUploadComplete,
}) => {
  const [isDragging, setIsDragging] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [uploadedRecording, setUploadedRecording] = useState<Recording | null>(null);
  const [stage, setStage] = useState<PipelineStage>('idle');
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const isSupportedFile = (candidate: File): boolean => {
    if (candidate.type.startsWith('audio/') || candidate.type.startsWith('video/')) {
      return true;
    }
    const ext = candidate.name.toLowerCase().slice(candidate.name.lastIndexOf('.'));
    return ALLOWED_EXTENSIONS.includes(ext);
  };

  const handleFileChange = (selectedFile: File) => {
    if (!isSupportedFile(selectedFile)) {
      setError('Please select a valid audio or video file (.mp3, .wav, .m4a, .mp4, .webm)');
      return;
    }
    setError(null);
    setFile(selectedFile);
    setUploadedRecording(null);
    setStage('idle');
    setProgress(0);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileChange(e.dataTransfer.files[0]);
    }
  };

  const isBusy = stage === 'uploading' || stage === 'processing';

  const handleUploadAndProcess = async () => {
    if (!file) return;
    setError(null);

    let recordingToProcess = uploadedRecording;

    try {
      // Step 1: Upload recording if not already stored
      if (!recordingToProcess) {
        setStage('uploading');
        setProgress(0);
        recordingToProcess = await meetingsApi.uploadRecording(meetingId, file, (p) => setProgress(p));
        setUploadedRecording(recordingToProcess);
      }

      // Step 2: Trigger processing pipeline
      setStage('processing');
      try {
        await meetingsApi.processMeeting(meetingId, recordingToProcess?.id);
      } catch (procErr: any) {
        // Idempotency: if recording is already queued or processing (e.g. 409 conflict), that is expected
        const status = procErr?.response?.status;
        const detail = (procErr?.response?.data?.detail || procErr?.message || '').toLowerCase();
        const isAlreadyProcessing = status === 409 || detail.includes('processing') || detail.includes('queued');

        if (!isAlreadyProcessing) {
          throw procErr;
        }
      }

      setStage('completed');
      onUploadComplete();
    } catch (err: any) {
      setStage('failed');
      setError(getErrorMessage(err));
    }
  };

  return (
    <div className="space-y-4 text-[#F8FAFC]">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          if (!isBusy) setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        onClick={() => !isBusy && fileInputRef.current?.click()}
        className={`border-2 border-dashed rounded-2xl p-8 text-center transition-all ${
          isBusy ? 'cursor-not-allowed opacity-90' : 'cursor-pointer'
        } ${
          isDragging
            ? 'border-[#3B82F6] bg-[#2563EB]/20'
            : file
            ? 'border-[#3B82F6] bg-[#123456]'
            : 'border-[#1D4E78] hover:border-[#3B82F6] bg-[#102C4D]'
        }`}
      >
        <input
          type="file"
          ref={fileInputRef}
          onChange={(e) => e.target.files?.[0] && handleFileChange(e.target.files[0])}
          accept="audio/*,video/*,.mp3,.wav,.m4a,.ogg,.mp4,.webm,.mov"
          className="hidden"
          disabled={isBusy}
        />

        <div className="flex flex-col items-center justify-center space-y-3">
          <div className="p-3.5 rounded-full bg-[#2563EB]/20 text-[#3B82F6] border border-[#2563EB]/40">
            {stage === 'processing' ? (
              <Loader2 className="w-8 h-8 animate-spin text-[#3B82F6]" />
            ) : stage === 'completed' ? (
              <CheckCircle2 className="w-8 h-8 text-[#22C55E]" />
            ) : file ? (
              <FileAudio className="w-8 h-8" />
            ) : (
              <Upload className="w-8 h-8" />
            )}
          </div>

          <div>
            {file ? (
              <div>
                <p className="text-[14px] sm:text-[15px] font-semibold text-[#F8FAFC]">{file.name}</p>
                <p className="text-[12px] text-[#8FA4BD] mt-0.5">
                  {(file.size / (1024 * 1024)).toFixed(2)} MB
                </p>
              </div>
            ) : (
              <div>
                <p className="text-[14px] sm:text-[15px] font-semibold text-[#F8FAFC]">
                  Click to upload or drag & drop recording
                </p>
                <p className="text-[12px] text-[#8FA4BD] mt-1">MP3, WAV, M4A, or MP4 audio/video file</p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Uploading Progress State */}
      {stage === 'uploading' && (
        <div className="space-y-2">
          <div className="flex justify-between text-[13px] text-[#B8C7DA] font-medium">
            <span className="flex items-center space-x-2">
              <Loader2 className="w-4 h-4 animate-spin text-[#3B82F6]" />
              <span>Uploading recording to storage...</span>
            </span>
            <span>{progress}%</span>
          </div>
          <div className="w-full h-2 bg-[#0A1B35] rounded-full overflow-hidden border border-[#1D4E78]">
            <div
              className="h-full bg-[#2563EB] transition-all duration-300"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      )}

      {/* Processing Active State */}
      {stage === 'processing' && (
        <div className="p-4 rounded-xl bg-[#2563EB]/15 border border-[#2563EB]/40 text-[#93C5FD] flex items-center space-x-3">
          <Loader2 className="w-5 h-5 animate-spin text-[#3B82F6] shrink-0" />
          <div>
            <p className="font-semibold text-[14px] text-[#F8FAFC]">Processing Pipeline Active</p>
            <p className="text-[12px] text-[#93C5FD]/80">
              Audio uploaded. Extracting speech transcript and AI meeting intelligence...
            </p>
          </div>
        </div>
      )}

      {/* Error / Failure State */}
      {error && stage === 'failed' && (
        <div className="flex items-center space-x-2 text-[13px] text-[#EF4444] bg-[#EF4444]/15 p-3 rounded-lg border border-[#EF4444]/40 font-medium">
          <AlertCircle className="w-4 h-4 flex-shrink-0 text-[#EF4444]" />
          <span>{error}</span>
        </div>
      )}

      {/* Action Controls */}
      {file && !isBusy && (
        <div className="flex justify-end space-x-3">
          <Button
            variant="ghost"
            onClick={(e) => {
              e.stopPropagation();
              setFile(null);
              setUploadedRecording(null);
              setStage('idle');
              setError(null);
            }}
          >
            Change File
          </Button>

          {stage === 'failed' ? (
            <Button onClick={handleUploadAndProcess} icon={<RotateCcw className="w-4 h-4" />}>
              Retry Processing
            </Button>
          ) : (
            <Button onClick={handleUploadAndProcess} icon={<Upload className="w-4 h-4" />}>
              Start Processing Pipeline
            </Button>
          )}
        </div>
      )}
    </div>
  );
};
