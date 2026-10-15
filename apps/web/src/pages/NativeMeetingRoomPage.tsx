import React, { useEffect, useState, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Copy,
  Check,
  ArrowLeft,
  Sparkles,
  PhoneOff,
  Clock,
  ShieldAlert,
  AlertTriangle,
  RefreshCw,
  X,
  Lock,
  Camera,
} from 'lucide-react';
import { meetingsApi } from '../api/meetings';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { getErrorMessage } from '../utils/error';
import { MeetingRoomState, ParticipantTrackState, NativeRoomJoinData, Meeting } from '../types';
import { mediaService } from '../services/mediaService';
import { PreJoinPreview } from '../components/meeting/PreJoinPreview';
import { VideoGrid } from '../components/meeting/VideoGrid';
import { MediaControlBar } from '../components/meeting/MediaControlBar';
import { ConnectionStatusOverlay } from '../components/meeting/ConnectionStatusOverlay';
import { ScreenShareStage } from '../components/meeting/ScreenShareStage';
import { MeetingChatPanel } from '../components/meeting/MeetingChatPanel';
import { ParticipantPanel } from '../components/meeting/ParticipantPanel';
import { RecordingConsentBanner } from '../components/meeting/RecordingConsentBanner';
import { DeviceSettingsModal } from '../components/meeting/DeviceSettingsModal';
import { ReactionsOverlay } from '../components/meeting/ReactionsOverlay';
import { Toast } from '../components/ui/Toast';

import { useAuthStore } from '../stores/useAuthStore';

export const NativeMeetingRoomPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { user } = useAuthStore();

  const [roomState, setRoomState] = useState<MeetingRoomState>('PREJOIN');
  const [loadingMeeting, setLoadingMeeting] = useState(true);
  const [meeting, setMeeting] = useState<Meeting | null>(null);
  const [joinData, setJoinData] = useState<NativeRoomJoinData | null>(null);
  const [participants, setParticipants] = useState<ParticipantTrackState[]>([]);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const [micOn, setMicOn] = useState(true);
  const [cameraOn, setCameraOn] = useState(true);
  const [cameraError, setCameraError] = useState<{
    code: string;
    message: string;
    title: string;
    type: 'denied' | 'in_use' | 'not_found' | 'generic';
  } | null>(null);
  const [retryingCamera, setRetryingCamera] = useState(false);
  const joinDataRef = useRef<NativeRoomJoinData | null>(null);
  joinDataRef.current = joinData;

  const [isScreenSharing, setIsScreenSharing] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [recordingLoading, setRecordingLoading] = useState(false);

  // Advanced Meeting Interactivity States
  const [isHandRaised, setIsHandRaised] = useState(false);
  const [activeReaction, setActiveReaction] = useState<string | null>(null);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' | 'info' } | null>(null);

  const [activePanel, setActivePanel] = useState<'none' | 'chat' | 'people'>('none');
  const [unreadChatCount, setUnreadChatCount] = useState(0);

  const [copiedLink, setCopiedLink] = useState(false);
  const [isEnding, setIsEnding] = useState(false);

  // Live Timer State
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  // Load meeting metadata on mount
  useEffect(() => {
    if (!id) return;

    const fetchMeetingInfo = async () => {
      setLoadingMeeting(true);
      setErrorMsg(null);
      try {
        const meetingData = await meetingsApi.getMeeting(id);
        setMeeting(meetingData);
        if (meetingData.status === 'RECORDING') {
          setIsRecording(true);
        }
      } catch (err: any) {
        setErrorMsg(getErrorMessage(err));
        setRoomState('ERROR');
      } finally {
        setLoadingMeeting(false);
      }
    };

    fetchMeetingInfo();
  }, [id]);

  // Live Meeting Duration Timer
  useEffect(() => {
    if (roomState !== 'CONNECTED') return;

    const timer = setInterval(() => {
      setElapsedSeconds((prev) => prev + 1);
    }, 1000);

    return () => clearInterval(timer);
  }, [roomState]);

  // Format Elapsed Time as HH:MM:SS or MM:SS
  const formatDuration = (seconds: number) => {
    const hrs = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;

    const pad = (n: number) => n.toString().padStart(2, '0');
    if (hrs > 0) return `${pad(hrs)}:${pad(mins)}:${pad(secs)}`;
    return `${pad(mins)}:${pad(secs)}`;
  };

  // Subscribe to mediaService state, participants, and chat broadcasts
  useEffect(() => {
    const unsubParticipants = mediaService.subscribeParticipants((pList) => {
      setParticipants(pList);

      const localP = pList.find((p) => p.isLocal);
      if (localP) {
        setIsScreenSharing(!!localP.isScreenSharing);
        setIsHandRaised(!!localP.isHandRaised);
        // Synchronize UI states directly with real live track status
        const isCamActive = !!(
          localP.isVideoEnabled &&
          localP.videoTrack &&
          localP.videoTrack.readyState === 'live' &&
          localP.videoTrack.enabled
        );
        const isMicActive = !!(
          localP.isAudioEnabled &&
          localP.audioTrack &&
          localP.audioTrack.readyState === 'live' &&
          localP.audioTrack.enabled
        );
        setCameraOn(isCamActive);
        setMicOn(isMicActive);
      }
    });

    const unsubStatus = mediaService.subscribeStatus((status) => {
      if (status === 'CONNECTED') setRoomState('CONNECTED');
      else if (status === 'CONNECTING') setRoomState('CONNECTING');
      else if (status === 'RECONNECTING') setRoomState('RECONNECTING');
      else if (status === 'DISCONNECTED') setRoomState((prev) => (prev === 'ENDED' ? 'ENDED' : 'DISCONNECTED'));
    });

    const unsubChat = mediaService.subscribeChatMessage(() => {
      if (activePanel !== 'chat') {
        setUnreadChatCount((prev) => prev + 1);
      }
    });

    return () => {
      unsubParticipants();
      unsubStatus();
      unsubChat();
    };
  }, [activePanel]);

  // Listen to browser permission state changes in real-time (e.g. user toggles Lock icon in address bar)
  useEffect(() => {
    const unsubCamPerm = mediaService.subscribePermissionChange('camera', async (newState) => {
      console.log('[NativeMeetingRoomPage] Camera permission state changed in browser:', newState);
      if (newState === 'granted') {
        setCameraError(null);
        if (joinDataRef.current) {
          console.log('[NativeMeetingRoomPage] Auto-starting camera on permission grant...');
          setRetryingCamera(true);
          const result = await mediaService.toggleVideo(true, joinDataRef.current.participant_identity);
          setRetryingCamera(false);
          if (result.success) {
            setCameraOn(true);
            setToast({
              type: 'success',
              message: 'Camera permission allowed! Video started.',
            });
          }
        }
      }
    });

    const unsubDeviceChange = mediaService.subscribeDeviceChange(() => {
      console.log('[NativeMeetingRoomPage] Media devices changed');
      mediaService.getAvailableDevices().catch(() => {});
    });

    return () => {
      unsubCamPerm();
      unsubDeviceChange();
    };
  }, []);

  // Poll backend for participant list updates & room recording status while connected
  useEffect(() => {
    if (roomState !== 'CONNECTED' || !id || !joinData) return;

    const interval = setInterval(async () => {
      try {
        const roomStatus = await meetingsApi.getNativeRoomStatus(id);
        if (roomStatus?.participants) {
          mediaService.updateRemoteParticipants(roomStatus.participants, joinData.participant_identity);
        }
        if (roomStatus?.room_status === 'CLOSED') {
          setRoomState('ENDED');
        }

        const meetingInfo = await meetingsApi.getMeeting(id);
        setIsRecording(meetingInfo.status === 'RECORDING');
      } catch (e) {
        console.warn('[NativeMeetingRoomPage] Status check error:', e);
      }
    }, 5000);

    return () => clearInterval(interval);
  }, [roomState, id, joinData]);

  // Handle Join Room from Pre-Join Screen
  const handleJoinFromPreview = async (initialAudio: boolean, initialVideo: boolean) => {
    if (!id) return;

    setRoomState('CONNECTING');
    setErrorMsg(null);
    setMicOn(initialAudio);
    setCameraOn(initialVideo);

    try {
      const data = await meetingsApi.joinNativeRoom(id);
      setJoinData(data);

      const roomStatus = await meetingsApi.getNativeRoomStatus(id);

      await mediaService.connectRoom({
        wsUrl: data.ws_url,
        token: data.token,
        identity: data.participant_identity,
        name: data.participant_name,
        isHost: data.is_host,
        initialAudio,
        initialVideo,
        existingParticipants: roomStatus?.participants || [],
      });
    } catch (err: any) {
      setErrorMsg(getErrorMessage(err));
      setRoomState('ERROR');
    }
  };

  const handleToggleMic = async () => {
    if (!joinData) return;
    const nextState = !micOn;
    console.log('[NativeMeetingRoomPage] Mic toggle clicked, nextState:', nextState);
    const result = await mediaService.toggleAudio(nextState, joinData.participant_identity);
    if (result.success) {
      setMicOn(nextState);
    } else {
      setMicOn(false);
      setToast({
        type: 'error',
        message: result.error || 'Failed to access microphone.',
      });
    }
  };

  const handleToggleCamera = async () => {
    if (!joinData) return;
    const nextState = !cameraOn;
    console.log('[NativeMeetingRoomPage] Camera toggle clicked, nextState:', nextState);

    if (!nextState) {
      // User is stopping video
      setCameraError(null);
      const result = await mediaService.toggleVideo(false, joinData.participant_identity);
      if (result.success) {
        setCameraOn(false);
      }
      return;
    }

    // User is starting video
    setRetryingCamera(true);
    const result = await mediaService.toggleVideo(true, joinData.participant_identity);
    setRetryingCamera(false);

    if (result.success) {
      setCameraOn(true);
      setCameraError(null);
      setToast({
        type: 'success',
        message: 'Camera started successfully!',
      });
    } else {
      setCameraOn(false);
      const errCode = result.errorCode || 'NOT_ALLOWED';
      let errType: 'denied' | 'in_use' | 'not_found' | 'generic' = 'generic';
      let errTitle = 'Camera Blocked';
      let errMsg = result.error || 'Failed to start camera.';

      if (errCode === 'NOT_ALLOWED') {
        errType = 'denied';
        errTitle = 'Camera Permission Blocked';
        errMsg =
          'Camera permission is blocked by browser or Windows privacy settings. Click the lock icon in your browser address bar to allow access, or check Windows Camera privacy settings, then click Retry.';
      } else if (errCode === 'NOT_READABLE') {
        errType = 'in_use';
        errTitle = 'Camera In Use / Blocked';
        errMsg =
          'Camera is being used by another app or blocked by Windows. Close Zoom/Teams/OBS and retry.';
      } else if (errCode === 'NOT_FOUND') {
        errType = 'not_found';
        errTitle = 'No Camera Detected';
        errMsg =
          'No camera detected. Check physical shutter, Fn camera key, and Device Manager.';
      }

      setCameraError({
        code: errCode,
        message: errMsg,
        title: errTitle,
        type: errType,
      });

      setToast({
        type: 'error',
        message: errMsg,
      });
    }
  };

  const handleRetryCamera = async () => {
    if (!joinData || retryingCamera) return;
    setRetryingCamera(true);
    console.log('[NativeMeetingRoomPage] Retrying camera start...');

    const result = await mediaService.toggleVideo(true, joinData.participant_identity);
    setRetryingCamera(false);

    if (result.success) {
      setCameraOn(true);
      setCameraError(null);
      setToast({
        type: 'success',
        message: 'Camera connected and video started!',
      });
    } else {
      setCameraOn(false);
      const errCode = result.errorCode || 'NOT_ALLOWED';
      let errType: 'denied' | 'in_use' | 'not_found' | 'generic' = 'generic';
      let errTitle = 'Camera Blocked';
      let errMsg = result.error || 'Failed to start camera.';

      if (errCode === 'NOT_ALLOWED') {
        errType = 'denied';
        errTitle = 'Camera Permission Blocked';
        errMsg =
          'Camera permission is blocked by browser or Windows privacy settings. Click the lock icon in your browser address bar to allow access, or check Windows Camera privacy settings, then click Retry.';
      } else if (errCode === 'NOT_READABLE') {
        errType = 'in_use';
        errTitle = 'Camera In Use / Blocked';
        errMsg =
          'Camera is being used by another app or blocked by Windows. Close Zoom/Teams/OBS and retry.';
      } else if (errCode === 'NOT_FOUND') {
        errType = 'not_found';
        errTitle = 'No Camera Detected';
        errMsg =
          'No camera detected. Check physical shutter, Fn camera key, and Device Manager.';
      }

      setCameraError({
        code: errCode,
        message: errMsg,
        title: errTitle,
        type: errType,
      });
    }
  };

  const handleToggleScreenShare = async () => {
    if (!joinData) return;

    if (isScreenSharing) {
      await mediaService.stopScreenShare(joinData.participant_identity);
    } else {
      await mediaService.startScreenShare(joinData.participant_identity);
    }
  };

  const handleToggleHandRaise = () => {
    const nextState = !isHandRaised;
    mediaService.toggleHandRaise(nextState);
    setIsHandRaised(nextState);
  };

  const handleSendReaction = (emoji: string) => {
    mediaService.sendReaction(emoji);
    setActiveReaction(emoji);
    setTimeout(() => {
      setActiveReaction(null);
    }, 3000);
  };

  const handleSwitchCamera = async (deviceId: string) => {
    await mediaService.switchCamera(deviceId);
  };

  const handleSwitchMicrophone = async (deviceId: string) => {
    await mediaService.switchMicrophone(deviceId);
  };

  const handleMuteParticipant = async (participantId: string) => {
    if (!id) return;
    try {
      await meetingsApi.muteParticipant(id, participantId);
    } catch (err: any) {
      alert(getErrorMessage(err));
    }
  };

  const handleKickParticipant = async (participantId: string) => {
    if (!id) return;
    try {
      await meetingsApi.kickParticipant(id, participantId);
    } catch (err: any) {
      alert(getErrorMessage(err));
    }
  };

  const handleToggleRecording = async () => {
    if (!id || !joinData?.is_host || recordingLoading) return;

    setRecordingLoading(true);
    try {
      if (isRecording) {
        await meetingsApi.stopNativeRecording(id);
        setIsRecording(false);
      } else {
        await meetingsApi.startNativeRecording(id);
        setIsRecording(true);
      }
    } catch (err: any) {
      alert(getErrorMessage(err));
    } finally {
      setRecordingLoading(false);
    }
  };

  const handleToggleChat = () => {
    setActivePanel((prev) => {
      if (prev === 'chat') return 'none';
      setUnreadChatCount(0);
      return 'chat';
    });
  };

  const handleTogglePeople = () => {
    setActivePanel((prev) => (prev === 'people' ? 'none' : 'people'));
  };

  const handleCopyLink = () => {
    const url = window.location.href;
    navigator.clipboard.writeText(url);
    setCopiedLink(true);
    setTimeout(() => setCopiedLink(false), 2000);
  };

  const handleLeaveRoom = async () => {
    if (id) {
      try {
        await meetingsApi.leaveNativeRoom(id);
      } catch (e) {
        console.error(e);
      }
    }
    mediaService.disconnect();
    setRoomState('DISCONNECTED');
  };

  const handleEndRoom = async () => {
    if (!id || !joinData?.is_host) return;
    if (!window.confirm('Are you sure you want to end this meeting for all participants?')) return;

    setIsEnding(true);
    try {
      await meetingsApi.endNativeRoom(id);
      mediaService.disconnect();
      setRoomState('ENDED');
    } catch (err: any) {
      alert(getErrorMessage(err));
      setIsEnding(false);
    }
  };

  // Find active screen sharer (if any)
  const activeSharer = participants.find((p) => p.isScreenSharing);

  // Render Pre-Join Preview Screen
  if (roomState === 'PREJOIN') {
    if (loadingMeeting) {
      return (
        <div className="min-h-[70vh] flex flex-col items-center justify-center space-y-4 text-[#F8FAFC]">
          <div className="w-12 h-12 border-4 border-[#3B82F6] border-t-transparent rounded-full animate-spin" />
          <h3 className="text-[18px] font-bold">Loading Meeting Information...</h3>
        </div>
      );
    }

    return (
      <PreJoinPreview
        meetingTitle={meeting?.title}
        userName={user?.full_name || user?.email?.split('@')[0] || 'Participant'}
        onJoin={handleJoinFromPreview}
        onBack={() => navigate('/meetings')}
      />
    );
  }

  // Render Overlay States (CONNECTING, RECONNECTING, DISCONNECTED, ENDED, ERROR)
  if (roomState !== 'CONNECTED') {
    return (
      <ConnectionStatusOverlay
        roomState={roomState}
        errorMessage={errorMsg}
        onReturnToMeetings={() => {
          mediaService.disconnect();
          navigate('/meetings');
        }}
        onRetry={() => {
          setRoomState('PREJOIN');
        }}
      />
    );
  }

  // Render Active Room UI
  return (
    <div className="max-w-7xl mx-auto space-y-5 animate-fade-in pb-8 text-[#F8FAFC]">
      {/* Reactions Overlay */}
      <ReactionsOverlay reaction={activeReaction} />

      {/* Device Settings Modal */}
      <DeviceSettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        onSwitchCamera={handleSwitchCamera}
        onSwitchMicrophone={handleSwitchMicrophone}
      />

      {/* Top Meeting Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-[#102C4D] p-5 sm:p-6 rounded-2xl border border-[#1D4E78] shadow-xl">
        <div className="space-y-1">
          <div className="flex items-center space-x-3">
            <button
              onClick={handleLeaveRoom}
              className="text-[#8FA4BD] hover:text-[#F8FAFC] transition-colors"
              title="Leave Room"
            >
              <ArrowLeft className="w-5 h-5" />
            </button>
            <h1 className="text-[22px] sm:text-[26px] font-bold text-[#F8FAFC] truncate">
              {meeting?.title || 'Native Meeting Room'}
            </h1>
            <Badge variant="primary" className="flex items-center space-x-1 shrink-0">
              <Sparkles className="w-3.5 h-3.5" />
              <span>Native Live</span>
            </Badge>
          </div>
          <div className="flex items-center space-x-3 text-[13px] sm:text-[14px] text-[#B8C7DA]">
            <span>
              Room ID: <span className="font-mono text-[#3B82F6]">{joinData?.room_id}</span>
            </span>
            <span>•</span>
            <div className="flex items-center space-x-1 font-mono text-[#22C55E]">
              <Clock className="w-3.5 h-3.5" />
              <span>{formatDuration(elapsedSeconds)}</span>
            </div>
            {joinData?.is_host && <span className="font-semibold text-[#22C55E]">• You are HOST</span>}
          </div>
        </div>

        <div className="flex items-center space-x-3 shrink-0">
          <Button
            variant="outline"
            size="sm"
            onClick={handleCopyLink}
            icon={copiedLink ? <Check className="text-[#22C55E]" /> : <Copy />}
          >
            {copiedLink ? 'Link Copied!' : 'Share Link'}
          </Button>

          {joinData?.is_host && (
            <Button variant="danger" size="sm" onClick={handleEndRoom} isLoading={isEnding}>
              End Meeting for All
            </Button>
          )}

          <Button variant="ghost" size="sm" onClick={handleLeaveRoom} icon={<PhoneOff />}>
            Leave
          </Button>
        </div>
      </div>

      {/* Recording Consent Banner (Visible to all participants when recording is active) */}
      {isRecording && <RecordingConsentBanner />}

      {/* Persistent Inline Camera Help Card on Error */}
      {cameraError && (
        <div
          className={`p-4 sm:p-5 rounded-2xl border transition-all shadow-xl animate-fade-in ${
            cameraError.type === 'denied'
              ? 'bg-[#0E1E38] border-[#EF4444]/50'
              : cameraError.type === 'in_use'
              ? 'bg-[#0E1E38] border-[#F59E0B]/50'
              : 'bg-[#0E1E38] border-[#3B82F6]/50'
          }`}
        >
          <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
            <div className="flex items-start space-x-3.5">
              <div
                className={`p-2 rounded-xl mt-0.5 shrink-0 ${
                  cameraError.type === 'denied'
                    ? 'bg-[#EF4444]/20 text-[#EF4444]'
                    : cameraError.type === 'in_use'
                    ? 'bg-[#F59E0B]/20 text-[#F59E0B]'
                    : 'bg-[#3B82F6]/20 text-[#3B82F6]'
                }`}
              >
                {cameraError.type === 'denied' ? (
                  <ShieldAlert className="w-5 h-5" />
                ) : cameraError.type === 'in_use' ? (
                  <AlertTriangle className="w-5 h-5" />
                ) : (
                  <Camera className="w-5 h-5" />
                )}
              </div>

              <div className="space-y-2">
                <div className="flex items-center space-x-2">
                  <h3 className="text-[15px] font-bold text-[#F8FAFC]">{cameraError.title}</h3>
                  <span
                    className={`px-2 py-0.5 rounded text-[11px] font-bold border ${
                      cameraError.type === 'denied'
                        ? 'bg-[#EF4444]/15 border-[#EF4444]/30 text-[#EF4444]'
                        : cameraError.type === 'in_use'
                        ? 'bg-[#F59E0B]/15 border-[#F59E0B]/30 text-[#FBBF24]'
                        : 'bg-[#3B82F6]/15 border-[#3B82F6]/30 text-[#60A5FA]'
                    }`}
                  >
                    {cameraError.code}
                  </span>
                </div>

                <p className="text-[13px] text-[#CBD5E1] leading-relaxed">{cameraError.message}</p>

                {cameraError.type === 'denied' && (
                  <div className="pt-2 grid grid-cols-1 md:grid-cols-3 gap-2.5 text-[12px] text-[#94A3B8]">
                    <div className="p-3 rounded-xl bg-[#06152F] border border-[#1D4E78]">
                      <div className="flex items-center space-x-1.5 font-semibold text-[#F8FAFC] mb-1">
                        <Lock className="w-3.5 h-3.5 text-[#3B82F6]" />
                        <span>1. Chrome Address Bar</span>
                      </div>
                      <p>
                        Click the <strong>padlock / tune icon</strong> next to localhost:5173, toggle <strong>Camera</strong> to <strong>Allow</strong>.
                      </p>
                    </div>

                    <div className="p-3 rounded-xl bg-[#06152F] border border-[#1D4E78]">
                      <div className="flex items-center space-x-1.5 font-semibold text-[#F8FAFC] mb-1">
                        <Sparkles className="w-3.5 h-3.5 text-[#38BDF8]" />
                        <span>2. Chrome Site Settings</span>
                      </div>
                      <p>
                        Open <code className="text-[#38BDF8] bg-[#102C4D] px-1 py-0.5 rounded">chrome://settings/content/camera</code> and remove localhost:5173 from "Not allowed".
                      </p>
                    </div>

                    <div className="p-3 rounded-xl bg-[#06152F] border border-[#1D4E78]">
                      <div className="flex items-center space-x-1.5 font-semibold text-[#F8FAFC] mb-1">
                        <ShieldAlert className="w-3.5 h-3.5 text-[#F59E0B]" />
                        <span>3. Windows Privacy</span>
                      </div>
                      <p>
                        Go to <strong>Windows Settings</strong> &rarr; <strong>Privacy & Security</strong> &rarr; <strong>Camera</strong>. Turn ON camera access for desktop apps.
                      </p>
                    </div>
                  </div>
                )}

                {cameraError.type === 'in_use' && (
                  <div className="p-3 rounded-xl bg-[#06152F] border border-[#1D4E78] text-[12px] text-[#94A3B8]">
                    <p className="text-[#F8FAFC] font-semibold mb-1">Camera Hardware In Use</p>
                    <p>
                      Another app (Zoom, Microsoft Teams, OBS Studio, Skype, or another browser window) currently holds an exclusive hardware lock on your webcam. Please close those applications, then click Retry.
                    </p>
                  </div>
                )}

                {cameraError.type === 'not_found' && (
                  <div className="p-3 rounded-xl bg-[#06152F] border border-[#1D4E78] text-[12px] text-[#94A3B8]">
                    <p className="text-[#F8FAFC] font-semibold mb-1">No Camera Device Found</p>
                    <p>
                      Check if your laptop has a physical privacy slider/shutter closed, a physical camera switch, or an Fn + Camera toggle key. Also verify your webcam is recognized in Windows Device Manager.
                    </p>
                  </div>
                )}
              </div>
            </div>

            <div className="flex items-center space-x-2 shrink-0 self-end md:self-start">
              <button
                onClick={handleRetryCamera}
                disabled={retryingCamera}
                className="flex items-center space-x-1.5 px-3.5 py-2 bg-[#2563EB] hover:bg-[#1D4ED8] disabled:opacity-50 text-white rounded-xl text-[13px] font-bold shadow-lg transition-all"
              >
                <RefreshCw className={`w-4 h-4 ${retryingCamera ? 'animate-spin' : ''}`} />
                <span>{retryingCamera ? 'Retrying Camera...' : 'Retry Camera'}</span>
              </button>
              <button
                onClick={() => setCameraError(null)}
                className="p-2 text-[#8FA4BD] hover:text-[#F8FAFC] transition-colors rounded-lg hover:bg-[#1D4E78]/50"
                title="Dismiss"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Main Stage & Right Panel Split Layout */}
      <div className="flex flex-col lg:flex-row gap-5 items-start">
        {/* Main Stage Container (Screen Share or Video Grid) */}
        <div className="flex-1 w-full bg-[#06152F] border border-[#1D4E78] rounded-2xl p-4 sm:p-6 min-h-[460px] flex flex-col justify-between shadow-2xl overflow-hidden relative">
          {activeSharer ? (
            <div className="space-y-4">
              <ScreenShareStage
                sharerName={activeSharer.name}
                isLocalSharer={activeSharer.isLocal}
                screenTrack={activeSharer.screenTrack || null}
                onStopSharing={handleToggleScreenShare}
              />
              <div className="pt-2 border-t border-[#1D4E78]">
                <VideoGrid participants={participants} />
              </div>
            </div>
          ) : (
            <VideoGrid participants={participants} />
          )}

          {/* Room Capability Info Footer */}
          <div className="mt-4 p-3.5 rounded-xl bg-[#102C4D]/80 border border-[#1D4E78] flex flex-col sm:flex-row items-center justify-between text-[13px] text-[#B8C7DA] gap-2">
            <div className="flex items-center space-x-2">
              <span className="w-2.5 h-2.5 rounded-full bg-[#22C55E] animate-ping" />
              <span>
                <strong>Production Video Platform:</strong> SFU multi-participant WebRTC, active speaker, recording & Whisper/AI active.
              </span>
            </div>
            <span className="font-mono text-[#3B82F6] text-[12px]">
              {participants.length} Participant{participants.length === 1 ? '' : 's'} Present
            </span>
          </div>
        </div>

        {/* Right Slide-over / Side Drawer Panel */}
        {activePanel !== 'none' && (
          <div className="w-full lg:w-auto shrink-0 animate-fade-in">
            {activePanel === 'chat' && joinData && (
              <MeetingChatPanel
                meetingId={id || ''}
                currentUserId={joinData.participant_identity}
                currentUserName={joinData.participant_name}
                onClose={() => setActivePanel('none')}
              />
            )}

            {activePanel === 'people' && (
              <ParticipantPanel
                participants={participants}
                isHost={!!joinData?.is_host}
                onClose={() => setActivePanel('none')}
                onEndRoom={handleEndRoom}
                onMuteParticipant={handleMuteParticipant}
                onKickParticipant={handleKickParticipant}
              />
            )}
          </div>
        )}
      </div>

      {/* Bottom Media Control Bar */}
      <MediaControlBar
        micOn={micOn}
        cameraOn={cameraOn}
        isScreenSharing={isScreenSharing}
        isRecording={isRecording}
        isRecordingLoading={recordingLoading}
        isHandRaised={isHandRaised}
        activePanel={activePanel}
        participantCount={participants.length}
        unreadChatCount={unreadChatCount}
        isHost={!!joinData?.is_host}
        isEnding={isEnding}
        onToggleMic={handleToggleMic}
        onToggleCamera={handleToggleCamera}
        onToggleScreenShare={handleToggleScreenShare}
        onToggleRecording={handleToggleRecording}
        onToggleHandRaise={handleToggleHandRaise}
        onSendReaction={handleSendReaction}
        onOpenSettings={() => setIsSettingsOpen(true)}
        onToggleChat={handleToggleChat}
        onTogglePeople={handleTogglePeople}
        onLeave={handleLeaveRoom}
        onEndRoom={handleEndRoom}
      />

      {/* Device Settings Modal */}
      <DeviceSettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        localIdentity={joinData?.participant_identity}
      />

      {/* Action Notification Toast */}
      {toast && (
        <Toast
          message={toast.message}
          type={toast.type}
          onClose={() => setToast(null)}
        />
      )}
    </div>
  );
};

