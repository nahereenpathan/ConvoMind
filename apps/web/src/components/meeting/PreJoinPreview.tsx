import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  Mic,
  MicOff,
  Video,
  VideoOff,
  ArrowLeft,
  ShieldAlert,
  Sparkles,
  Camera,
  Volume2,
  RefreshCw,
  HelpCircle,
  Play,
  Activity,
  AlertTriangle,
  Lock,
} from 'lucide-react';
import { Card } from '../ui/Card';
import { Button } from '../ui/Button';
import { MediaDeviceStatus, MediaDeviceOption, mediaService } from '../../services/mediaService';

interface PreJoinPreviewProps {
  meetingTitle?: string;
  userName: string;
  onJoin: (audioEnabled: boolean, videoEnabled: boolean) => void;
  onBack: () => void;
}

type CameraUIState =
  | 'INITIALIZING'
  | 'READY'
  | 'PERMISSION_REQUIRED'
  | 'UNAVAILABLE'
  | 'BUSY'
  | 'OVERCONSTRAINED'
  | 'MUTED'
  | 'AUDIO_ONLY';

export const PreJoinPreview: React.FC<PreJoinPreviewProps> = ({
  meetingTitle,
  userName,
  onJoin,
  onBack,
}) => {
  const videoElementRef = useRef<HTMLVideoElement | null>(null);
  const isJoiningRef = useRef<boolean>(false);

  const [stream, setStream] = useState<MediaStream | null>(null);
  const [deviceStatus, setDeviceStatus] = useState<MediaDeviceStatus>({
    audioAllowed: false,
    videoAllowed: false,
    audioEnabled: false,
    videoEnabled: false,
    hasAudioHardware: true,
    hasVideoHardware: true,
    error: null,
    errorCode: null,
  });

  const [micOn, setMicOn] = useState(true);
  const [cameraOn, setCameraOn] = useState(true);
  const [initializing, setInitializing] = useState(true);
  const [retrying, setRetrying] = useState(false);

  // Audio level meter state (0 - 100)
  const [micLevel, setMicLevel] = useState<number>(0);

  // Speaker test audio state
  const [isPlayingTestSound, setIsPlayingTestSound] = useState(false);

  // Browser Permission Guide Modal / Accordion
  const [showPermissionHelp, setShowPermissionHelp] = useState(false);

  // Available devices
  const [cameras, setCameras] = useState<MediaDeviceOption[]>([]);
  const [microphones, setMicrophones] = useState<MediaDeviceOption[]>([]);
  const [speakers, setSpeakers] = useState<MediaDeviceOption[]>([]);

  const [selectedCamera, setSelectedCamera] = useState<string>('');
  const [selectedMic, setSelectedMic] = useState<string>('');
  const [selectedSpeaker, setSelectedSpeaker] = useState<string>('');

  /**
   * Robust video element attachment and playback handler.
   * Handles srcObject assignment, autoPlay, muted, playsInline, and playback promises.
   */
  const attachStreamToVideo = useCallback((mediaStream: MediaStream | null, isCameraActive: boolean) => {
    const el = videoElementRef.current;
    if (!el) return;

    if (
      mediaStream &&
      isCameraActive &&
      mediaStream.getVideoTracks().some((t) => t.readyState === 'live')
    ) {
      if (el.srcObject !== mediaStream) {
        el.srcObject = mediaStream;
      }
      const playPromise = el.play();
      if (playPromise !== undefined) {
        playPromise.catch((err) => {
          if (err.name !== 'AbortError') {
            console.warn('[PreJoinPreview] Video play error:', err);
          }
        });
      }
    } else {
      el.srcObject = null;
    }
  }, []);

  // Update video element srcObject whenever stream or camera state changes
  useEffect(() => {
    attachStreamToVideo(stream, cameraOn && deviceStatus.videoAllowed);
  }, [stream, cameraOn, deviceStatus.videoAllowed, attachStreamToVideo]);

  /**
   * Determine exact, fine-grained UI state for camera preview
   */
  const getCameraState = (): {
    status: CameraUIState;
    title: string;
    description?: string;
  } => {
    if (initializing || retrying) {
      return {
        status: 'INITIALIZING',
        title: 'Initializing Media Devices...',
        description: 'Checking camera, microphone, and browser permissions.',
      };
    }
    if (!deviceStatus.hasVideoHardware || deviceStatus.errorCode === 'NOT_FOUND') {
      return {
        status: 'UNAVAILABLE',
        title: 'No Camera Detected',
        description: 'No camera detected on your system. Continuing with audio only.',
      };
    }
    if (deviceStatus.errorCode === 'NOT_ALLOWED') {
      return {
        status: 'PERMISSION_REQUIRED',
        title: 'Camera Permission Blocked',
        description: 'Camera permission blocked by browser or Windows privacy settings. Click the lock icon in your address bar to allow, then click Retry.',
      };
    }
    if (deviceStatus.errorCode === 'NOT_READABLE') {
      return {
        status: 'BUSY',
        title: 'Camera In Use',
        description: 'Camera is in use by another app (Zoom/Teams/OBS) or blocked by the OS. Close it and retry.',
      };
    }
    if (deviceStatus.errorCode === 'OVERCONSTRAINED') {
      return {
        status: 'OVERCONSTRAINED',
        title: 'Camera Setting Unsupported',
        description: 'Selected camera unavailable, switching to default camera.',
      };
    }
    if (deviceStatus.errorCode === 'SECURITY') {
      return {
        status: 'PERMISSION_REQUIRED',
        title: 'Security Policy Blocked',
        description: 'Camera blocked by security policy or insecure context.',
      };
    }
    if (
      deviceStatus.videoAllowed &&
      cameraOn &&
      stream?.getVideoTracks().some((t) => t.readyState === 'live' && t.enabled)
    ) {
      return {
        status: 'READY',
        title: 'Camera Ready',
      };
    }
    if (deviceStatus.videoAllowed && !cameraOn) {
      return {
        status: 'MUTED',
        title: 'Camera Muted',
        description: 'Your camera is off. Click "Camera ON" below to start video.',
      };
    }
    if (deviceStatus.error) {
      return {
        status: 'PERMISSION_REQUIRED',
        title: 'Camera Blocked',
        description: deviceStatus.error,
      };
    }
    return {
      status: 'AUDIO_ONLY',
      title: 'Audio-Only Mode',
      description: 'Camera preview is disabled.',
    };
  };

  const cameraState = getCameraState();

  /**
   * Initialize or reload devices and media streams.
   * On Retry or ForceVideo, video is explicitly requested and errors are cleared.
   */
  const loadMediaAndDevices = useCallback(
    async (isRetry: boolean = false, forceVideo: boolean = false) => {
      if (isRetry) {
        setRetrying(true);
        // Clear previous error state on explicit user retry
        setDeviceStatus((prev) => ({
          ...prev,
          error: null,
          errorCode: null,
        }));
      } else {
        setInitializing(true);
      }

      // Check current browser permission state when supported
      const permState = await mediaService.checkPermissionState('camera');
      if (permState !== 'unsupported') {
        console.log('[PreJoinPreview] Browser camera permission status:', permState);
      }

      // Explicitly decide if video should be attempted
      const shouldAttemptVideo = isRetry || forceVideo || cameraOn;

      const res = await mediaService.requestMediaPermissions(
        micOn,
        shouldAttemptVideo,
        selectedCamera || undefined,
        selectedMic || undefined
      );

      // Re-enumerate devices after permissions are acquired to populate accurate labels
      const dev = await mediaService.getAvailableDevices();

      setStream(res.stream);
      setDeviceStatus(res.status);
      setMicOn(res.status.audioEnabled);
      setCameraOn(res.status.videoEnabled);

      setCameras(dev.cameras);
      setMicrophones(dev.microphones);
      setSpeakers(dev.speakers);

      if ((!selectedCamera || selectedCamera === '') && dev.cameras.length > 0) {
        setSelectedCamera(dev.cameras[0].deviceId);
      }
      if ((!selectedMic || selectedMic === '') && dev.microphones.length > 0) {
        setSelectedMic(dev.microphones[0].deviceId);
      }
      if ((!selectedSpeaker || selectedSpeaker === '') && dev.speakers.length > 0) {
        setSelectedSpeaker(dev.speakers[0].deviceId);
      }

      setInitializing(false);
      setRetrying(false);
    },
    [micOn, cameraOn, selectedCamera, selectedMic, selectedSpeaker]
  );

  useEffect(() => {
    let mounted = true;

    const init = async () => {
      await loadMediaAndDevices(false, true);
    };

    init();

    // Listen to physical device connect/disconnect
    const unsubDeviceChange = mediaService.subscribeDeviceChange(() => {
      if (mounted) {
        loadMediaAndDevices(false, false);
      }
    });

    // Listen to real-time browser permission changes (e.g. user clicks Allow on lock icon)
    const unsubCamPerm = mediaService.subscribePermissionChange('camera', (newState) => {
      console.log('[PreJoinPreview] Camera permission state changed in browser:', newState);
      if (mounted && newState === 'granted') {
        loadMediaAndDevices(true, true);
      }
    });

    const unsubMicPerm = mediaService.subscribePermissionChange('microphone', (newState) => {
      console.log('[PreJoinPreview] Microphone permission state changed in browser:', newState);
      if (mounted && newState === 'granted') {
        loadMediaAndDevices(true, false);
      }
    });

    return () => {
      mounted = false;
      unsubDeviceChange();
      unsubCamPerm();
      unsubMicPerm();
      // Only release local stream if user navigates back and does NOT join room
      if (!isJoiningRef.current) {
        mediaService.releaseLocalStream();
      }
    };
  }, []);

  // Real-time audio level meter for microphone input
  useEffect(() => {
    if (stream && micOn && deviceStatus.audioAllowed) {
      const stopMeter = mediaService.startAudioMeter(stream, (level) => {
        setMicLevel(level);
      });
      return () => {
        stopMeter();
        setMicLevel(0);
      };
    } else {
      setMicLevel(0);
    }
  }, [stream, micOn, deviceStatus.audioAllowed]);

  /**
   * Explicit user action: Retry camera & audio initialization
   */
  const handleRetry = async () => {
    await loadMediaAndDevices(true, true);
  };

  /**
   * Camera device dropdown switch
   */
  const handleCameraChange = async (deviceId: string) => {
    setSelectedCamera(deviceId);
    if (cameraOn && deviceStatus.videoAllowed) {
      const success = await mediaService.switchCamera(deviceId);
      if (success) {
        const activeStream = mediaService.getLocalStream();
        if (activeStream) {
          setStream(new MediaStream(activeStream.getTracks()));
        }
      } else {
        // Fall back to default camera if requested camera cannot be opened
        console.warn('[PreJoinPreview] Camera switch failed; falling back to default camera.');
        const fallbackRes = await mediaService.requestCameraTrack();
        if (fallbackRes.track) {
          const activeStream = mediaService.getLocalStream();
          if (activeStream) {
            setStream(new MediaStream(activeStream.getTracks()));
          }
        }
      }
    }
  };

  /**
   * Microphone device dropdown switch
   */
  const handleMicChange = async (deviceId: string) => {
    setSelectedMic(deviceId);
    if (micOn && deviceStatus.audioAllowed) {
      const success = await mediaService.switchMicrophone(deviceId);
      if (success) {
        const activeStream = mediaService.getLocalStream();
        if (activeStream) {
          setStream(new MediaStream(activeStream.getTracks()));
        }
      }
    }
  };

  /**
   * Speaker device dropdown switch
   */
  const handleSpeakerChange = async (deviceId: string) => {
    setSelectedSpeaker(deviceId);
    await mediaService.switchSpeaker(deviceId);
  };

  /**
   * Microphone toggle
   */
  const toggleMic = () => {
    if (!deviceStatus.audioAllowed) return;
    const nextState = !micOn;
    if (stream) {
      const audioTrack = stream.getAudioTracks()[0];
      if (audioTrack) audioTrack.enabled = nextState;
    }
    setMicOn(nextState);
  };

  /**
   * Camera toggle - acts as explicit user gesture to request camera if off/blocked
   */
  const toggleCamera = async () => {
    if (!deviceStatus.hasVideoHardware) return;

    if (!cameraOn || !deviceStatus.videoAllowed) {
      // User is explicitly clicking to turn camera ON: trigger user-initiated getUserMedia
      setRetrying(true);
      setDeviceStatus((prev) => ({ ...prev, error: null, errorCode: null }));

      const camRes = await mediaService.requestCameraTrack(selectedCamera || undefined);
      const dev = await mediaService.getAvailableDevices();
      setCameras(dev.cameras);

      if (camRes.track && camRes.track.readyState === 'live') {
        const activeStream = mediaService.getLocalStream();
        setStream(activeStream ? new MediaStream(activeStream.getTracks()) : null);
        setCameraOn(true);
        setDeviceStatus((prev) => ({
          ...prev,
          videoAllowed: true,
          videoEnabled: true,
          error: null,
          errorCode: null,
        }));
      } else {
        setCameraOn(false);
        setDeviceStatus((prev) => ({
          ...prev,
          videoAllowed: false,
          videoEnabled: false,
          error:
            camRes.errorMessage ||
            'Camera permission was denied. Click the lock icon in your address bar to allow access, then click Retry.',
          errorCode: camRes.errorCode || 'NOT_ALLOWED',
        }));
      }
      setRetrying(false);
    } else {
      // User is explicitly muting camera
      setCameraOn(false);
      if (stream) {
        const videoTrack = stream.getVideoTracks()[0];
        if (videoTrack) videoTrack.enabled = false;
      }
    }
  };

  /**
   * Test audio output chime
   */
  const handleTestSpeaker = async () => {
    setIsPlayingTestSound(true);
    await mediaService.playTestSound(selectedSpeaker);
    setTimeout(() => {
      setIsPlayingTestSound(false);
    }, 700);
  };

  /**
   * Join room handler - marks isJoiningRef so streams are not killed on unmount
   */
  const handleJoinClick = () => {
    isJoiningRef.current = true;
    const isVideoAllowed = cameraOn && deviceStatus.videoAllowed;
    if (!isVideoAllowed && stream) {
      stream.getVideoTracks().forEach((track) => {
        try {
          track.stop();
        } catch (e) {
          console.warn('[PreJoinPreview] Error stopping video track on join:', e);
        }
      });
    }
    onJoin(micOn && deviceStatus.audioAllowed, isVideoAllowed);
  };

  /**
   * Back button handler - releases local media stream
   */
  const handleBackClick = () => {
    mediaService.releaseLocalStream();
    onBack();
  };

  // Check if an actionable notice banner should be displayed
  const shouldShowNoticeBanner =
    deviceStatus.error &&
    cameraState.status !== 'READY' &&
    cameraState.status !== 'MUTED';

  return (
    <div className="max-w-3xl mx-auto space-y-6 animate-fade-in text-[#F8FAFC]">
      <button
        onClick={handleBackClick}
        className="flex items-center space-x-2 text-[14px] font-semibold text-[#8FA4BD] hover:text-[#F8FAFC] transition-colors"
      >
        <ArrowLeft className="w-4 h-4" />
        <span>Back to Meetings</span>
      </button>

      <Card className="bg-[#102C4D] border border-[#1D4E78] p-6 space-y-6 shadow-2xl">
        <div className="space-y-1 text-center sm:text-left">
          <div className="flex items-center justify-between">
            <h2 className="text-[22px] sm:text-[24px] font-bold text-[#F8FAFC]">
              Ready to Join {meetingTitle ? `"${meetingTitle}"` : 'Live Meeting'}?
            </h2>
            <span className="hidden sm:flex items-center space-x-1.5 px-3 py-1 rounded-full bg-[#2563EB]/20 text-[#3B82F6] text-[12px] font-semibold border border-[#2563EB]/40">
              <Sparkles className="w-3.5 h-3.5" />
              <span>ConvoMind Real-Time</span>
            </span>
          </div>
          <p className="text-[14px] text-[#B8C7DA]">
            Verify your camera, microphone, and speaker audio before entering the room.
          </p>
        </div>

        {/* Actionable Device Notice Card if unresolved camera/audio issue exists */}
        {shouldShowNoticeBanner && (
          <div
            className={`p-4 rounded-xl border flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 text-[13px] ${
              deviceStatus.errorCode === 'NOT_FOUND'
                ? 'bg-[#1E293B]/90 border-[#3B82F6]/40 text-[#94A3B8]'
                : deviceStatus.errorCode === 'NOT_READABLE'
                ? 'bg-[#F59E0B]/15 border-[#F59E0B]/40 text-[#F8FAFC]'
                : 'bg-[#EF4444]/15 border-[#EF4444]/40 text-[#F8FAFC]'
            }`}
          >
            <div className="flex items-start space-x-3">
              {deviceStatus.errorCode === 'NOT_FOUND' ? (
                <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5 text-[#3B82F6]" />
              ) : deviceStatus.errorCode === 'NOT_READABLE' ? (
                <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5 text-[#F59E0B]" />
              ) : (
                <ShieldAlert className="w-5 h-5 shrink-0 mt-0.5 text-[#EF4444]" />
              )}

              <div className="space-y-1">
                <div className="flex items-center space-x-2">
                  <p
                    className={`font-semibold ${
                      deviceStatus.errorCode === 'NOT_FOUND'
                        ? 'text-[#60A5FA]'
                        : deviceStatus.errorCode === 'NOT_READABLE'
                        ? 'text-[#FBBF24]'
                        : 'text-[#EF4444]'
                    }`}
                  >
                    {deviceStatus.errorCode === 'NOT_FOUND'
                      ? 'Audio-Only Mode'
                      : deviceStatus.errorCode === 'NOT_READABLE'
                      ? 'Camera In Use / Busy'
                      : 'Device Permission Notice'}
                  </p>
                  {deviceStatus.audioAllowed && (
                    <span className="px-2 py-0.5 bg-[#22C55E]/20 text-[#22C55E] text-[11px] font-bold rounded border border-[#22C55E]/40">
                      Mic Ready
                    </span>
                  )}
                </div>
                <p className="text-[#CBD5E1] leading-relaxed">{deviceStatus.error}</p>
              </div>
            </div>

            <div className="flex items-center space-x-2 shrink-0 self-end sm:self-auto">
              <button
                onClick={handleRetry}
                disabled={retrying}
                className="flex items-center space-x-1.5 px-3 py-1.5 bg-[#123456] hover:bg-[#1A4570] border border-[#1D4E78] rounded-lg text-[12px] font-bold text-[#F8FAFC] transition-colors"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${retrying ? 'animate-spin' : ''}`} />
                <span>{retrying ? 'Checking...' : 'Retry'}</span>
              </button>

              <button
                onClick={() => setShowPermissionHelp((prev) => !prev)}
                className="flex items-center space-x-1 px-2.5 py-1.5 text-[12px] text-[#8FA4BD] hover:text-[#F8FAFC] transition-colors"
                title="Browser permission instructions"
              >
                <HelpCircle className="w-4 h-4" />
                <span>Help</span>
              </button>
            </div>
          </div>
        )}

        {/* Detailed Browser Permission Guide Modal / Accordion */}
        {showPermissionHelp && (
          <div className="p-4 rounded-xl bg-[#06152F] border border-[#1D4E78] text-[13px] text-[#CBD5E1] space-y-3 animate-fade-in shadow-xl">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2 font-bold text-[#F8FAFC]">
                <Lock className="w-4 h-4 text-[#3B82F6]" />
                <span>How to allow Camera and Microphone access:</span>
              </div>
              <button
                onClick={() => setShowPermissionHelp(false)}
                className="text-[12px] text-[#8FA4BD] hover:text-white"
              >
                Close
              </button>
            </div>

            <div className="space-y-2 text-[#94A3B8] text-[12.5px] leading-relaxed">
              <div className="p-2.5 rounded-lg bg-[#102C4D]/60 border border-[#1D4E78]/50">
                <p className="font-semibold text-[#F8FAFC] mb-1">1. Chrome / Edge Address Bar (Quickest):</p>
                <p>
                  Click the <strong>Padlock / Tune icon</strong> on the left side of your browser URL bar (next to localhost or domain), toggle <strong>Camera</strong> and <strong>Microphone</strong> to <strong>Allow</strong>, then click the <strong>Retry</strong> button.
                </p>
              </div>

              <div className="p-2.5 rounded-lg bg-[#102C4D]/60 border border-[#1D4E78]/50">
                <p className="font-semibold text-[#F8FAFC] mb-1">2. Chrome Site Settings (If permanently blocked):</p>
                <p>
                  Go to <code className="text-[#38BDF8] bg-[#0A1B35] px-1 py-0.5 rounded">chrome://settings/content/camera</code> in a new tab. Ensure "Sites can ask to use your camera" is selected and this app is not listed under "Not allowed to use your camera".
                </p>
              </div>

              <div className="p-2.5 rounded-lg bg-[#102C4D]/60 border border-[#1D4E78]/50">
                <p className="font-semibold text-[#F8FAFC] mb-1">3. Windows 10/11 Camera Privacy Settings:</p>
                <p>
                  Open <strong>Windows Settings</strong> &rarr; <strong>Privacy & Security</strong> &rarr; <strong>Camera</strong>. Ensure <strong>Camera access</strong> and <strong>Let desktop apps access your camera</strong> are switched ON.
                </p>
              </div>

              <div className="p-2.5 rounded-lg bg-[#102C4D]/60 border border-[#1D4E78]/50">
                <p className="font-semibold text-[#F8FAFC] mb-1">4. Close conflicting apps:</p>
                <p>
                  If another application like Zoom, Teams, Skype, or OBS is currently using your camera, close it and click <strong>Retry</strong>.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Video Preview Container */}
        <div className="relative aspect-video bg-[#06152F] rounded-2xl overflow-hidden border border-[#1D4E78] flex items-center justify-center shadow-inner">
          {/* Permanent Video Element in DOM - guarantees videoElementRef is never null */}
          <video
            ref={videoElementRef}
            autoPlay
            playsInline
            muted
            className={`w-full h-full object-cover transform -scale-x-100 ${
              cameraState.status === 'READY' ? 'block' : 'hidden'
            }`}
          />

          {/* Fallback & Status Display when camera is not in READY state */}
          {cameraState.status !== 'READY' && (
            <div className="flex flex-col items-center space-y-3 z-10 px-4 text-center">
              {cameraState.status === 'INITIALIZING' ? (
                <div className="w-12 h-12 border-4 border-[#3B82F6] border-t-transparent rounded-full animate-spin" />
              ) : (
                <div className="w-24 h-24 rounded-full bg-[#123456] border-2 border-[#1D4E78] flex items-center justify-center text-3xl font-bold text-[#F8FAFC] shadow-lg">
                  {(userName || 'U').charAt(0).toUpperCase()}
                </div>
              )}
              <div className="space-y-1">
                <p className="text-[15px] font-bold text-[#F8FAFC]">{cameraState.title}</p>
                {cameraState.description && (
                  <p className="text-[12.5px] text-[#8FA4BD] max-w-sm mx-auto leading-relaxed">
                    {cameraState.description}
                  </p>
                )}
              </div>
            </div>
          )}

          {/* User Name & Live Mic Level Indicator Overlay */}
          <div className="absolute bottom-3 left-3 bg-[#06152F]/90 backdrop-blur-md px-3 py-1.5 rounded-lg border border-[#1D4E78] text-[13px] font-semibold text-[#F8FAFC] flex items-center space-x-3 shadow-lg z-20">
            <div className="flex items-center space-x-2">
              <span
                className={`w-2 h-2 rounded-full ${
                  micOn && deviceStatus.audioAllowed ? 'bg-[#22C55E] animate-pulse' : 'bg-[#EF4444]'
                }`}
              />
              <span>{userName} (You)</span>
            </div>

            {/* Visual 4-bar Audio Volume Meter */}
            {micOn && deviceStatus.audioAllowed && (
              <div
                className="flex items-center space-x-0.5 border-l border-[#1D4E78] pl-2.5"
                title="Microphone Audio Level"
              >
                <Activity className="w-3.5 h-3.5 text-[#22C55E] mr-1" />
                {[15, 35, 60, 85].map((threshold, idx) => (
                  <div
                    key={idx}
                    className={`w-1 rounded-full transition-all duration-75 ${
                      micLevel >= threshold ? 'bg-[#22C55E] h-3.5' : 'bg-[#1D4E78] h-1.5'
                    }`}
                  />
                ))}
              </div>
            )}
          </div>

          {/* Top-Right Mode Badge */}
          <div className="absolute top-3 right-3 flex items-center space-x-2 z-20">
            {cameraState.status === 'READY' ? (
              <span className="px-2.5 py-1 rounded-md bg-[#22C55E]/20 border border-[#22C55E]/40 text-[11px] font-bold text-[#22C55E]">
                Camera Ready
              </span>
            ) : cameraState.status === 'INITIALIZING' ? (
              <span className="px-2.5 py-1 rounded-md bg-[#3B82F6]/20 border border-[#3B82F6]/40 text-[11px] font-bold text-[#60A5FA]">
                Initializing...
              </span>
            ) : cameraState.status === 'PERMISSION_REQUIRED' ? (
              <span className="px-2.5 py-1 rounded-md bg-[#EF4444]/20 border border-[#EF4444]/40 text-[11px] font-bold text-[#EF4444]">
                Permission Blocked
              </span>
            ) : cameraState.status === 'BUSY' ? (
              <span className="px-2.5 py-1 rounded-md bg-[#F59E0B]/20 border border-[#F59E0B]/40 text-[11px] font-bold text-[#FBBF24]">
                Camera Busy
              </span>
            ) : cameraState.status === 'MUTED' ? (
              <span className="px-2.5 py-1 rounded-md bg-[#1E293B] border border-[#1D4E78] text-[11px] font-bold text-[#94A3B8]">
                Camera Muted
              </span>
            ) : (
              <span className="px-2.5 py-1 rounded-md bg-[#0A1B35]/85 border border-[#1D4E78] text-[11px] font-bold text-[#94A3B8]">
                Audio-Only Mode
              </span>
            )}
          </div>
        </div>

        {/* Device Selection Selectors */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 p-3.5 bg-[#06152F] border border-[#1D4E78] rounded-xl text-[13px]">
          {/* Camera Input Selector */}
          <div>
            <label className="flex items-center justify-between font-semibold text-[#B8C7DA] mb-1">
              <div className="flex items-center space-x-1.5">
                <Camera className="w-3.5 h-3.5 text-[#3B82F6]" />
                <span>Camera</span>
              </div>
              {!deviceStatus.hasVideoHardware && (
                <span className="text-[11px] text-[#8FA4BD]">None</span>
              )}
            </label>
            <select
              value={selectedCamera}
              onChange={(e) => handleCameraChange(e.target.value)}
              disabled={!deviceStatus.hasVideoHardware || cameras.length === 0}
              className="w-full bg-[#123456] border border-[#1D4E78] text-[#F8FAFC] rounded-lg p-2 focus:outline-none focus:border-[#3B82F6] disabled:opacity-50"
            >
              {cameras.length === 0 ? (
                <option value="">No Camera Found</option>
              ) : (
                cameras.map((c) => (
                  <option key={c.deviceId} value={c.deviceId}>
                    {c.label}
                  </option>
                ))
              )}
            </select>
          </div>

          {/* Microphone Input Selector */}
          <div>
            <label className="flex items-center justify-between font-semibold text-[#B8C7DA] mb-1">
              <div className="flex items-center space-x-1.5">
                <Mic className="w-3.5 h-3.5 text-[#22C55E]" />
                <span>Microphone</span>
              </div>
              {micLevel > 10 && (
                <span className="text-[11px] text-[#22C55E] animate-pulse">Input Detected</span>
              )}
            </label>
            <select
              value={selectedMic}
              onChange={(e) => handleMicChange(e.target.value)}
              disabled={microphones.length === 0}
              className="w-full bg-[#123456] border border-[#1D4E78] text-[#F8FAFC] rounded-lg p-2 focus:outline-none focus:border-[#3B82F6]"
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

          {/* Speaker Output Selector with Test Sound Button */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="flex items-center space-x-1.5 font-semibold text-[#B8C7DA]">
                <Volume2 className="w-3.5 h-3.5 text-[#818CF8]" />
                <span>Speaker</span>
              </label>
              <button
                type="button"
                onClick={handleTestSpeaker}
                disabled={isPlayingTestSound}
                className="text-[11px] text-[#3B82F6] hover:text-[#60A5FA] font-bold flex items-center space-x-1 transition-colors"
                title="Play test audio chime"
              >
                <Play className={`w-3 h-3 ${isPlayingTestSound ? 'animate-spin' : ''}`} />
                <span>{isPlayingTestSound ? 'Playing...' : 'Test Speaker'}</span>
              </button>
            </div>
            <select
              value={selectedSpeaker}
              onChange={(e) => handleSpeakerChange(e.target.value)}
              className="w-full bg-[#123456] border border-[#1D4E78] text-[#F8FAFC] rounded-lg p-2 focus:outline-none focus:border-[#3B82F6]"
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
        </div>

        {/* Controls and Join Actions */}
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4 pt-2">
          {/* Audio / Video Toggles */}
          <div className="flex items-center space-x-3 w-full sm:w-auto justify-center">
            <button
              onClick={toggleMic}
              disabled={!deviceStatus.audioAllowed}
              className={`flex items-center space-x-2 px-4 py-2.5 rounded-xl border text-[14px] font-semibold transition-all ${
                micOn && deviceStatus.audioAllowed
                  ? 'bg-[#123456] border-[#1D4E78] text-[#F8FAFC] hover:bg-[#1A4570]'
                  : 'bg-[#EF4444]/20 border-[#EF4444]/40 text-[#EF4444]'
              }`}
            >
              {micOn && deviceStatus.audioAllowed ? (
                <>
                  <Mic className="w-4 h-4 text-[#22C55E]" />
                  <span>Mic ON</span>
                </>
              ) : (
                <>
                  <MicOff className="w-4 h-4 text-[#EF4444]" />
                  <span>Mic Muted</span>
                </>
              )}
            </button>

            <button
              onClick={toggleCamera}
              disabled={!deviceStatus.hasVideoHardware}
              className={`flex items-center space-x-2 px-4 py-2.5 rounded-xl border text-[14px] font-semibold transition-all ${
                cameraOn && deviceStatus.videoAllowed
                  ? 'bg-[#123456] border-[#1D4E78] text-[#F8FAFC] hover:bg-[#1A4570]'
                  : 'bg-[#EF4444]/20 border-[#EF4444]/40 text-[#EF4444]'
              }`}
            >
              {cameraOn && deviceStatus.videoAllowed ? (
                <>
                  <Video className="w-4 h-4 text-[#3B82F6]" />
                  <span>Camera ON</span>
                </>
              ) : (
                <>
                  <VideoOff className="w-4 h-4 text-[#EF4444]" />
                  <span>
                    {!deviceStatus.hasVideoHardware
                      ? 'No Camera'
                      : !deviceStatus.videoAllowed
                      ? 'Camera Blocked'
                      : 'Camera Off'}
                  </span>
                </>
              )}
            </button>
          </div>

          {/* Join Meeting Action */}
          <Button
            onClick={handleJoinClick}
            size="lg"
            className="w-full sm:w-auto min-w-[200px] bg-[#3B82F6] hover:bg-[#2563EB] text-white font-bold shadow-lg"
          >
            {deviceStatus.videoAllowed && cameraOn ? 'Join Meeting' : 'Join (Audio Only)'}
          </Button>
        </div>
      </Card>
    </div>
  );
};
