/**
 * Production Real-Time Media Provider Manager for ConvoMind (Phase 4).
 *
 * Supports Real-Time WebRTC Video, Audio, Screen Sharing, Active Speaker Detection,
 * Device Hot-Swapping, Hand Raises, Emoji Reactions, and LiveKit SFU Integration.
 */

import { ParticipantTrackState, MediaDeviceOption } from '../types';
export type { MediaDeviceOption };

export interface MediaDeviceStatus {
  audioAllowed: boolean;
  videoAllowed: boolean;
  audioEnabled: boolean;
  videoEnabled: boolean;
  hasAudioHardware: boolean;
  hasVideoHardware: boolean;
  error?: string | null;
  errorCode?: 'NOT_ALLOWED' | 'NOT_FOUND' | 'NOT_READABLE' | 'OVERCONSTRAINED' | 'SECURITY' | 'UNKNOWN' | null;
}

export type MediaEventCallback = (participants: ParticipantTrackState[]) => void;
export type StatusEventCallback = (status: string) => void;
export type ChatEventCallback = (message: any) => void;
export type ReactionEventCallback = (reaction: { senderId: string; senderName: string; emoji: string }) => void;
export type DeviceChangeCallback = () => void;

class ConvoMindMediaService {
  private localStream: MediaStream | null = null;
  private localScreenStream: MediaStream | null = null;
  private isMockMode: boolean = false;
  private participantsMap: Map<string, ParticipantTrackState> = new Map();
  private onParticipantsChangedCallbacks: Set<MediaEventCallback> = new Set();
  private onRoomStatusChangedCallbacks: Set<StatusEventCallback> = new Set();
  private onChatMessageCallbacks: Set<ChatEventCallback> = new Set();
  private onReactionCallbacks: Set<ReactionEventCallback> = new Set();
  private onDeviceChangeCallbacks: Set<DeviceChangeCallback> = new Set();
  private livekitRoom: any = null;

  // Selected device state
  private selectedCameraId: string = '';
  private selectedMicId: string = '';
  private selectedSpeakerId: string = '';

  // Audio Context for volume metering and audio chimes
  private audioContext: AudioContext | null = null;
  private audioMeterSource: MediaStreamAudioSourceNode | null = null;
  private audioMeterAnalyser: AnalyserNode | null = null;
  private audioMeterAnimId: number | null = null;

  constructor() {
    if (typeof window !== 'undefined' && navigator?.mediaDevices?.addEventListener) {
      navigator.mediaDevices.addEventListener('devicechange', () => {
        this.notifyDeviceChange();
      });
    }
  }

  /**
   * Enumerate available media input and output devices.
   */
  async getAvailableDevices(): Promise<{
    cameras: MediaDeviceOption[];
    microphones: MediaDeviceOption[];
    speakers: MediaDeviceOption[];
  }> {
    if (typeof navigator === 'undefined' || !navigator.mediaDevices?.enumerateDevices) {
      return { cameras: [], microphones: [], speakers: [] };
    }

    try {
      const devices = await navigator.mediaDevices.enumerateDevices();
      const cameras: MediaDeviceOption[] = [];
      const microphones: MediaDeviceOption[] = [];
      const speakers: MediaDeviceOption[] = [];

      devices.forEach((d) => {
        if (d.kind === 'videoinput') {
          cameras.push({
            deviceId: d.deviceId,
            label: d.label || `Camera ${cameras.length + 1}`,
          });
        } else if (d.kind === 'audioinput') {
          microphones.push({
            deviceId: d.deviceId,
            label: d.label || `Microphone ${microphones.length + 1}`,
          });
        } else if (d.kind === 'audiooutput') {
          speakers.push({
            deviceId: d.deviceId,
            label: d.label || `Speaker ${speakers.length + 1}`,
          });
        }
      });

      return { cameras, microphones, speakers };
    } catch (e) {
      console.warn('[MediaService] Device enumeration error:', e);
      return { cameras: [], microphones: [], speakers: [] };
    }
  }

  /**
   * Check browser permission status for camera or microphone using Permissions API when available.
   */
  async checkPermissionState(name: 'camera' | 'microphone'): Promise<'granted' | 'prompt' | 'denied' | 'unsupported'> {
    try {
      if (typeof navigator !== 'undefined' && navigator.permissions?.query) {
        const status = await navigator.permissions.query({ name: name as any });
        return status.state;
      }
    } catch {
      // Browsers like Firefox or Safari may not support camera/microphone query
    }
    return 'unsupported';
  }

  /**
   * Subscribe to camera and microphone permission status changes via Permissions API.
   * Invokes callback when user toggles permission in browser lock icon / site settings.
   */
  subscribePermissionChange(name: 'camera' | 'microphone', callback: (state: PermissionState) => void): () => void {
    if (typeof navigator === 'undefined' || !navigator.permissions?.query) {
      return () => {};
    }

    let permissionStatus: PermissionStatus | null = null;
    const listener = () => {
      if (permissionStatus) {
        callback(permissionStatus.state);
      }
    };

    navigator.permissions
      .query({ name: name as any })
      .then((status) => {
        permissionStatus = status;
        status.addEventListener('change', listener);
        status.onchange = listener;
      })
      .catch((e) => {
        console.debug(`[MediaService] Permissions query for ${name} unsupported:`, e);
      });

    return () => {
      if (permissionStatus) {
        permissionStatus.removeEventListener('change', listener);
        permissionStatus.onchange = null;
      }
    };
  }

  /**
   * Request camera access independently.
   * Tests availability, handles invalid device IDs gracefully, releases old tracks,
   * and provides clear error classification.
   */
  async requestCameraTrack(preferredDeviceId?: string): Promise<{
    track: MediaStreamTrack | null;
    errorCode: MediaDeviceStatus['errorCode'];
    errorMessage: string | null;
  }> {
    if (typeof navigator === 'undefined' || !navigator.mediaDevices?.getUserMedia) {
      return {
        track: null,
        errorCode: 'SECURITY',
        errorMessage: 'Media devices are not supported or blocked in this browser environment.',
      };
    }

    // Stop and release any obsolete video tracks first to prevent hardware locks
    if (this.localStream) {
      const oldTracks = this.localStream.getVideoTracks();
      oldTracks.forEach((t) => {
        try {
          t.stop();
          this.localStream?.removeTrack(t);
        } catch (e) {
          console.warn('[MediaService] Stop old video track error:', e);
        }
      });
    }

    // Diagnostic pre-check before calling getUserMedia
    const permState = await this.checkPermissionState('camera');
    const availableDevices = await this.getAvailableDevices();
    console.log('[MediaService.requestCameraTrack] Pre-check diagnostics:', {
      permissionsQueryState: permState,
      availableVideoDevicesCount: availableDevices.cameras.length,
      cameras: availableDevices.cameras.map((c) => ({ id: c.deviceId, label: c.label })),
      preferredDeviceId,
    });

    let track: MediaStreamTrack | null = null;
    let errorCode: MediaDeviceStatus['errorCode'] = null;
    let errorMessage: string | null = null;

    // 1. Try with preferred camera device ID if valid (not empty, not generic "Camera 1")
    const hasValidDeviceId =
      preferredDeviceId &&
      preferredDeviceId.trim() !== '' &&
      preferredDeviceId !== 'default' &&
      !preferredDeviceId.startsWith('Camera ');

    if (hasValidDeviceId) {
      try {
        console.log('[MediaService] Requesting camera with ideal deviceId:', preferredDeviceId);
        const stream = await navigator.mediaDevices.getUserMedia({
          video: {
            deviceId: { ideal: preferredDeviceId },
            width: { ideal: 1280 },
            height: { ideal: 720 },
          },
        });
        track = stream.getVideoTracks()[0] || null;
      } catch (err: any) {
        console.warn('[MediaService] Specific camera request failed, falling back to default camera:', err?.name);
      }
    }

    // 2. Initial / fallback check: request default camera with { video: true }
    if (!track) {
      try {
        console.log('[MediaService] Requesting default camera: getUserMedia({ video: true })');
        const stream = await navigator.mediaDevices.getUserMedia({ video: true });
        track = stream.getVideoTracks()[0] || null;
      } catch (err: any) {
        console.error('[MediaService] Camera getUserMedia({ video: true }) failed:', {
          name: err?.name,
          message: err?.message,
          constraint: err?.constraint,
        });

        if (err?.name === 'NotAllowedError' || err?.name === 'PermissionDeniedError') {
          errorCode = 'NOT_ALLOWED';
          errorMessage =
            'Camera permission blocked by browser or Windows privacy settings. Click the lock icon in your browser address bar to allow access, or check your Windows Camera privacy settings, then click Retry.';
        } else if (err?.name === 'NotFoundError' || err?.name === 'DevicesNotFoundError') {
          errorCode = 'NOT_FOUND';
          errorMessage = 'No camera detected. Check physical shutter, Fn camera key, and Device Manager.';
        } else if (err?.name === 'NotReadableError' || err?.name === 'TrackStartError') {
          errorCode = 'NOT_READABLE';
          errorMessage =
            'Camera is being used by another app or blocked by Windows. Close Zoom/Teams/OBS and retry.';
        } else if (err?.name === 'OverconstrainedError') {
          errorCode = 'OVERCONSTRAINED';
          errorMessage = 'Selected camera unavailable, switching to default camera.';
        } else if (err?.name === 'SecurityError') {
          errorCode = 'SECURITY';
          errorMessage = 'Camera blocked by security policy or insecure context.';
        } else {
          errorCode = 'UNKNOWN';
          errorMessage = err?.message || 'Camera is unavailable or failed to start.';
        }
      }
    }

    if (track && track.readyState === 'live') {
      this.selectedCameraId = track.getSettings().deviceId || preferredDeviceId || '';

      if (this.localStream) {
        this.localStream.addTrack(track);
      } else {
        this.localStream = new MediaStream([track]);
      }
      return { track, errorCode: null, errorMessage: null };
    }

    return { track: null, errorCode, errorMessage };
  }

  /**
   * Request microphone access independently without touching camera tracks.
   * Releases previous audio tracks before acquiring new ones.
   */
  async requestMicrophoneTrack(preferredMicId?: string): Promise<{
    track: MediaStreamTrack | null;
    errorCode: MediaDeviceStatus['errorCode'];
    errorMessage: string | null;
  }> {
    if (typeof navigator === 'undefined' || !navigator.mediaDevices?.getUserMedia) {
      return {
        track: null,
        errorCode: 'SECURITY',
        errorMessage: 'Media devices are not supported or blocked in this browser environment.',
      };
    }

    // Stop and release any obsolete audio tracks first
    if (this.localStream) {
      const oldTracks = this.localStream.getAudioTracks();
      oldTracks.forEach((t) => {
        try {
          t.stop();
          this.localStream?.removeTrack(t);
        } catch (e) {
          console.warn('[MediaService] Stop old audio track error:', e);
        }
      });
    }

    let track: MediaStreamTrack | null = null;
    let errorCode: MediaDeviceStatus['errorCode'] = null;
    let errorMessage: string | null = null;

    const hasValidMicId =
      preferredMicId &&
      preferredMicId.trim() !== '' &&
      preferredMicId !== 'default' &&
      !preferredMicId.startsWith('Microphone ');

    if (hasValidMicId) {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: {
            deviceId: { ideal: preferredMicId },
            echoCancellation: true,
            noiseSuppression: true,
          },
        });
        track = stream.getAudioTracks()[0] || null;
      } catch (err: any) {
        console.warn('[MediaService] Specific microphone request failed, falling back to default:', err?.name);
      }
    }

    if (!track) {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: { echoCancellation: true, noiseSuppression: true },
        });
        track = stream.getAudioTracks()[0] || null;
      } catch (err: any) {
        console.warn('[MediaService] Microphone getUserMedia failed:', err?.name, err);
        if (err?.name === 'NotAllowedError' || err?.name === 'PermissionDeniedError') {
          errorCode = 'NOT_ALLOWED';
          errorMessage = 'Microphone permission was denied. Please allow microphone access in browser settings.';
        } else if (err?.name === 'NotFoundError' || err?.name === 'DevicesNotFoundError') {
          errorCode = 'NOT_FOUND';
          errorMessage = 'No microphone device detected on your system. Please connect an audio input device.';
        } else if (err?.name === 'NotReadableError' || err?.name === 'TrackStartError') {
          errorCode = 'NOT_READABLE';
          errorMessage = 'Microphone is currently in use by another application. Close other apps and try again.';
        } else {
          errorCode = 'UNKNOWN';
          errorMessage = 'Microphone access failed. Please check your system audio settings.';
        }
      }
    }

    if (track && track.readyState === 'live') {
      this.selectedMicId = track.getSettings().deviceId || preferredMicId || '';

      if (this.localStream) {
        this.localStream.addTrack(track);
      } else {
        this.localStream = new MediaStream([track]);
      }
      return { track, errorCode: null, errorMessage: null };
    }

    return { track: null, errorCode, errorMessage };
  }

  /**
   * Request browser media permissions and initialize camera/mic preview stream.
   * Evaluates camera and microphone independently so camera failure NEVER disables microphone.
   */
  async requestMediaPermissions(
    audioInitial: boolean = true,
    videoInitial: boolean = true,
    cameraId?: string,
    micId?: string
  ): Promise<{ stream: MediaStream | null; status: MediaDeviceStatus }> {
    if (cameraId) this.selectedCameraId = cameraId;
    if (micId) this.selectedMicId = micId;

    if (typeof navigator === 'undefined' || !navigator.mediaDevices?.getUserMedia) {
      return {
        stream: null,
        status: {
          audioAllowed: false,
          videoAllowed: false,
          audioEnabled: false,
          videoEnabled: false,
          hasAudioHardware: false,
          hasVideoHardware: false,
          error: 'Media devices are not supported or blocked in this browser environment.',
          errorCode: 'SECURITY',
        },
      };
    }

    // 1. Probe available hardware
    const available = await this.getAvailableDevices();
    const hasVideoHardware = available.cameras.length > 0;
    const hasAudioHardware = available.microphones.length > 0;

    let audioAllowed = false;
    let videoAllowed = false;
    let audioTrack: MediaStreamTrack | null = null;
    let videoTrack: MediaStreamTrack | null = null;
    let errorMsg: string | null = null;
    let errorCode: MediaDeviceStatus['errorCode'] = null;

    // 2. Request microphone track independently
    if (audioInitial) {
      const micRes = await this.requestMicrophoneTrack(micId || this.selectedMicId);
      audioTrack = micRes.track;
      audioAllowed = !!audioTrack;
      if (!audioAllowed && micRes.errorMessage) {
        errorMsg = micRes.errorMessage;
        errorCode = micRes.errorCode;
      }
    } else {
      audioAllowed = false;
    }

    // 3. Request camera track independently
    if (videoInitial) {
      const camRes = await this.requestCameraTrack(cameraId || this.selectedCameraId);
      videoTrack = camRes.track;
      videoAllowed = !!videoTrack;
      if (!videoAllowed && camRes.errorMessage) {
        // Video error message takes precedence when microphone is allowed
        errorMsg = camRes.errorMessage;
        errorCode = camRes.errorCode;
      }
    } else if (!hasVideoHardware && videoInitial) {
      errorCode = 'NOT_FOUND';
      errorMsg = 'No camera hardware detected on your device. Continuing with audio only.';
    }

    // 4. Update track enabled status according to requested flags
    if (audioTrack) {
      audioTrack.enabled = audioInitial;
    }
    if (videoTrack) {
      videoTrack.enabled = videoInitial;
    }

    return {
      stream: this.localStream,
      status: {
        audioAllowed,
        videoAllowed,
        audioEnabled: audioAllowed && audioInitial,
        videoEnabled: videoAllowed && videoInitial,
        hasAudioHardware,
        hasVideoHardware,
        error: errorMsg,
        errorCode,
      },
    };
  }

  /**
   * Get active local media stream.
   */
  getLocalStream(): MediaStream | null {
    return this.localStream;
  }

  /**
   * Release and stop all local preview and meeting media tracks.
   */
  releaseLocalStream() {
    this.stopAudioMeter();
    if (this.localStream) {
      this.localStream.getTracks().forEach((track) => {
        try {
          track.stop();
        } catch (e) {
          console.warn('[MediaService] Track stop error:', e);
        }
      });
      this.localStream = null;
    }
  }

  /**
   * Start real-time audio level meter for microphone preview / speaking detection.
   * Returns a cleanup function to stop the meter.
   */
  startAudioMeter(stream: MediaStream, onLevelChange: (level: number) => void): () => void {
    this.stopAudioMeter();

    const audioTrack = stream.getAudioTracks()[0];
    if (!audioTrack || !audioTrack.enabled) {
      onLevelChange(0);
      return () => {};
    }

    try {
      const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;
      if (!AudioContextClass) return () => {};

      const ctx = new AudioContextClass();
      if (ctx.state === 'suspended') {
        ctx.resume().catch(() => {});
      }

      const analyser = ctx.createAnalyser();
      analyser.fftSize = 256;
      analyser.smoothingTimeConstant = 0.5;

      const source = ctx.createMediaStreamSource(new MediaStream([audioTrack]));
      source.connect(analyser);

      this.audioContext = ctx;
      this.audioMeterSource = source;
      this.audioMeterAnalyser = analyser;

      const buffer = new Uint8Array(analyser.frequencyBinCount);

      const checkLevel = () => {
        if (!this.audioMeterAnalyser) return;
        this.audioMeterAnalyser.getByteFrequencyData(buffer);
        let sum = 0;
        for (let i = 0; i < buffer.length; i++) {
          sum += buffer[i];
        }
        const avg = sum / buffer.length;
        // Normalize 0..100
        const percentage = Math.min(100, Math.round((avg / 128) * 100));
        onLevelChange(percentage);
        this.audioMeterAnimId = requestAnimationFrame(checkLevel);
      };

      this.audioMeterAnimId = requestAnimationFrame(checkLevel);

      return () => {
        this.stopAudioMeter();
        onLevelChange(0);
      };
    } catch (e) {
      console.warn('[MediaService] Audio meter initialization error:', e);
      return () => {};
    }
  }

  /**
   * Stop audio level meter and release Web Audio API context.
   */
  stopAudioMeter() {
    if (this.audioMeterAnimId !== null) {
      cancelAnimationFrame(this.audioMeterAnimId);
      this.audioMeterAnimId = null;
    }
    if (this.audioMeterSource) {
      try {
        this.audioMeterSource.disconnect();
      } catch (e) {}
      this.audioMeterSource = null;
    }
    if (this.audioMeterAnalyser) {
      try {
        this.audioMeterAnalyser.disconnect();
      } catch (e) {}
      this.audioMeterAnalyser = null;
    }
    if (this.audioContext) {
      try {
        this.audioContext.close();
      } catch (e) {}
      this.audioContext = null;
    }
  }

  /**
   * Play a clean two-tone speaker test chime (523Hz -> 659Hz) to verify audio output.
   */
  async playTestSound(speakerDeviceId?: string): Promise<boolean> {
    try {
      const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;
      if (!AudioContextClass) return false;

      const ctx = new AudioContextClass();
      if (ctx.state === 'suspended') {
        await ctx.resume();
      }

      const targetSpeaker = speakerDeviceId || this.selectedSpeakerId;
      if (targetSpeaker && typeof (ctx.destination as any).setSinkId === 'function') {
        try {
          await (ctx.destination as any).setSinkId(targetSpeaker);
        } catch (sinkErr) {
          console.warn('[MediaService] setSinkId on AudioDestination failed:', sinkErr);
        }
      }

      const playTone = (freq: number, start: number, duration: number) => {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();

        osc.type = 'sine';
        osc.frequency.setValueAtTime(freq, ctx.currentTime + start);

        gain.gain.setValueAtTime(0.001, ctx.currentTime + start);
        gain.gain.exponentialRampToValueAtTime(0.2, ctx.currentTime + start + 0.03);
        gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + start + duration);

        osc.connect(gain);
        gain.connect(ctx.destination);

        osc.start(ctx.currentTime + start);
        osc.stop(ctx.currentTime + start + duration);
      };

      // Tone 1: C5 (523.25 Hz)
      playTone(523.25, 0, 0.2);
      // Tone 2: E5 (659.25 Hz)
      playTone(659.25, 0.22, 0.35);

      setTimeout(() => {
        try {
          ctx.close();
        } catch (e) {}
      }, 700);

      return true;
    } catch (e) {
      console.warn('[MediaService] Play test sound error:', e);
      return false;
    }
  }

  /**
   * Select audio output device (speaker) and apply to media elements where supported.
   */
  async switchSpeaker(deviceId: string, mediaElements?: (HTMLAudioElement | HTMLVideoElement)[]): Promise<boolean> {
    this.selectedSpeakerId = deviceId;
    let applied = false;

    if (mediaElements && Array.isArray(mediaElements)) {
      for (const el of mediaElements) {
        if (el && typeof (el as any).setSinkId === 'function') {
          try {
            await (el as any).setSinkId(deviceId);
            applied = true;
          } catch (e) {
            console.warn('[MediaService] setSinkId on element error:', e);
          }
        }
      }
    }

    return applied;
  }

  private getLocalIdentity(providedIdentity?: string): string {
    if (providedIdentity) return providedIdentity;
    for (const p of this.participantsMap.values()) {
      if (p.isLocal) return p.identity;
    }
    return '';
  }

  /**
   * Switch active camera device mid-call or in preview.
   */
  async switchCamera(deviceId: string, localIdentity?: string): Promise<boolean> {
    this.selectedCameraId = deviceId;
    const identity = this.getLocalIdentity(localIdentity);

    try {
      if (this.livekitRoom?.localParticipant) {
        await this.livekitRoom.switchActiveDevice('videoinput', deviceId);
        return true;
      }

      const camRes = await this.requestCameraTrack(deviceId);
      if (!camRes.track) return false;

      const localP = this.participantsMap.get(identity);
      if (localP) {
        localP.videoTrack = camRes.track;
        localP.isVideoEnabled = true;
        this.notifyParticipants();
      }
      return true;
    } catch (err: any) {
      console.warn('[MediaService] Switch camera failed:', err);
      return false;
    }
  }

  /**
   * Switch active microphone device mid-call or in preview.
   */
  async switchMicrophone(deviceId: string, localIdentity?: string): Promise<boolean> {
    this.selectedMicId = deviceId;
    const identity = this.getLocalIdentity(localIdentity);

    try {
      if (this.livekitRoom?.localParticipant) {
        await this.livekitRoom.switchActiveDevice('audioinput', deviceId);
        return true;
      }

      const micRes = await this.requestMicrophoneTrack(deviceId);
      if (!micRes.track) return false;

      const localP = this.participantsMap.get(identity);
      if (localP) {
        localP.audioTrack = micRes.track;
        localP.isAudioEnabled = true;
        this.notifyParticipants();
      }
      return true;
    } catch (err: any) {
      console.warn('[MediaService] Switch microphone failed:', err);
      return false;
    }
  }

  /**
   * Connect to Real-Time Meeting Room (LiveKit SFU or Fallback).
   */
  async connectRoom(params: {
    wsUrl: string;
    token: string;
    identity: string;
    name: string;
    isHost: boolean;
    initialAudio: boolean;
    initialVideo: boolean;
    existingParticipants?: any[];
  }): Promise<void> {
    const { token, identity, name, isHost, initialAudio, initialVideo, existingParticipants } = params;

    this.isMockMode = token.startsWith('mock_lk_token_') || params.wsUrl.includes('mock');

    // If joining without video (audio-only mode), cleanly stop and remove any leftover preview video tracks
    if (!initialVideo && this.localStream) {
      const oldVideoTracks = this.localStream.getVideoTracks();
      oldVideoTracks.forEach((track) => {
        try {
          track.stop();
          this.localStream?.removeTrack(track);
        } catch (e) {
          console.warn('[MediaService] Leftover preview video track stop error on connect:', e);
        }
      });
    }

    const localVideoTrack = this.localStream?.getVideoTracks()[0] || null;
    const localAudioTrack = this.localStream?.getAudioTracks()[0] || null;

    if (localAudioTrack) localAudioTrack.enabled = initialAudio;
    if (localVideoTrack) localVideoTrack.enabled = initialVideo;

    const localParticipant: ParticipantTrackState = {
      id: identity,
      identity,
      name,
      role: isHost ? 'host' : 'attendee',
      isLocal: true,
      isAudioEnabled: initialAudio && !!localAudioTrack,
      isVideoEnabled: initialVideo && !!localVideoTrack,
      isScreenSharing: false,
      isSpeaking: false,
      isHandRaised: false,
      reaction: null,
      audioTrack: localAudioTrack,
      videoTrack: localVideoTrack,
      screenTrack: null,
      joinedAt: new Date().toISOString(),
    };

    this.participantsMap.clear();
    this.participantsMap.set(identity, localParticipant);

    if (this.isMockMode) {
      this.notifyStatus('CONNECTED');

      if (existingParticipants && Array.isArray(existingParticipants)) {
        existingParticipants.forEach((p) => {
          const pIdentity = p.user_id || p.media_identity || p.id;
          if (pIdentity && pIdentity !== identity) {
            this.participantsMap.set(pIdentity, {
              id: pIdentity,
              identity: pIdentity,
              name: p.name || 'Participant',
              role: p.role === 'host' ? 'host' : 'attendee',
              isLocal: false,
              isAudioEnabled: true,
              isVideoEnabled: false,
              isScreenSharing: false,
              isSpeaking: false,
              isHandRaised: false,
              reaction: null,
              joinedAt: p.joined_at || new Date().toISOString(),
            });
          }
        });
      }
      this.notifyParticipants();
      return;
    }

    // LiveKit SFU Connection Mode
    try {
      this.notifyStatus('CONNECTING');
      const LiveKit = await import('livekit-client');
      const room = new LiveKit.Room({
        adaptiveStream: true,
        dynacast: true,
      });

      this.livekitRoom = room;

      room.on(LiveKit.RoomEvent.ParticipantConnected, (participant: any) => {
        this.addLiveKitParticipant(participant);
      });

      room.on(LiveKit.RoomEvent.ParticipantDisconnected, (participant: any) => {
        this.participantsMap.delete(participant.identity);
        this.notifyParticipants();
      });

      room.on(LiveKit.RoomEvent.TrackSubscribed, (_track: any, _publication: any, participant: any) => {
        this.addLiveKitParticipant(participant);
      });

      room.on(LiveKit.RoomEvent.TrackUnsubscribed, (_track: any, _publication: any, participant: any) => {
        this.addLiveKitParticipant(participant);
      });

      room.on(LiveKit.RoomEvent.ActiveSpeakersChanged, (speakers: any[]) => {
        const speakingIdentities = new Set(speakers.map((s) => s.identity));
        this.participantsMap.forEach((p) => {
          p.isSpeaking = speakingIdentities.has(p.identity);
        });
        this.notifyParticipants();
      });

      room.on(LiveKit.RoomEvent.DataReceived, (payload: Uint8Array, _participant: any) => {
        try {
          const strData = new TextDecoder().decode(payload);
          const parsed = JSON.parse(strData);

          if (parsed.type === 'HAND_RAISE') {
            const p = this.participantsMap.get(parsed.senderId);
            if (p) {
              p.isHandRaised = !!parsed.raised;
              this.notifyParticipants();
            }
          } else if (parsed.type === 'REACTION') {
            const p = this.participantsMap.get(parsed.senderId);
            if (p) {
              p.reaction = parsed.emoji;
              this.notifyParticipants();
              setTimeout(() => {
                if (p.reaction === parsed.emoji) {
                  p.reaction = null;
                  this.notifyParticipants();
                }
              }, 4000);
            }
            this.notifyReaction(parsed);
          } else {
            this.notifyChatMessage(parsed);
          }
        } catch (e) {
          console.warn('[MediaService] DataReceived parse error:', e);
        }
      });

      room.on(LiveKit.RoomEvent.Reconnecting, () => {
        this.notifyStatus('RECONNECTING');
      });

      room.on(LiveKit.RoomEvent.Reconnected, () => {
        this.notifyStatus('CONNECTED');
      });

      room.on(LiveKit.RoomEvent.Disconnected, () => {
        this.notifyStatus('DISCONNECTED');
      });

      await room.connect(params.wsUrl, token);
      this.notifyStatus('CONNECTED');

      // Publish local tracks
      if (this.localStream) {
        if (localAudioTrack) await room.localParticipant.publishTrack(localAudioTrack);
        if (localVideoTrack) await room.localParticipant.publishTrack(localVideoTrack);
      }

      // Existing remote participants
      room.remoteParticipants.forEach((participant: any) => {
        this.addLiveKitParticipant(participant);
      });

      this.notifyParticipants();
    } catch (err) {
      console.warn('[MediaService] LiveKit SFU Connection failed, falling back to mock mode:', err);
      this.isMockMode = true;
      this.notifyStatus('CONNECTED');
      this.notifyParticipants();
    }
  }

  private addLiveKitParticipant(participant: any) {
    let videoTrack: MediaStreamTrack | null = null;
    let audioTrack: MediaStreamTrack | null = null;
    let screenTrack: MediaStreamTrack | null = null;

    participant.videoTrackPublications.forEach((pub: any) => {
      if (pub.source === 'screen_share' && pub.track?.mediaStreamTrack) {
        screenTrack = pub.track.mediaStreamTrack;
      } else if (pub.track?.mediaStreamTrack) {
        videoTrack = pub.track.mediaStreamTrack;
      }
    });

    participant.audioTrackPublications.forEach((pub: any) => {
      if (pub.track?.mediaStreamTrack) audioTrack = pub.track.mediaStreamTrack;
    });

    this.participantsMap.set(participant.identity, {
      id: participant.identity,
      identity: participant.identity,
      name: participant.name || participant.identity,
      role: 'attendee',
      isLocal: false,
      isAudioEnabled: !!audioTrack,
      isVideoEnabled: !!videoTrack,
      isScreenSharing: !!screenTrack,
      isSpeaking: participant.isSpeaking || false,
      isHandRaised: false,
      reaction: null,
      audioTrack,
      videoTrack,
      screenTrack,
      joinedAt: new Date().toISOString(),
    });

    this.notifyParticipants();
  }

  /**
   * Toggle hand raised state and broadcast to room.
   */
  toggleHandRaise(raised: boolean = true, localIdentity?: string) {
    const identity = this.getLocalIdentity(localIdentity);
    const localP = this.participantsMap.get(identity);
    if (localP) {
      localP.isHandRaised = raised;
      this.notifyParticipants();
    }

    const payload = {
      type: 'HAND_RAISE',
      senderId: identity,
      raised,
    };

    if (this.livekitRoom?.localParticipant) {
      try {
        const encoded = new TextEncoder().encode(JSON.stringify(payload));
        this.livekitRoom.localParticipant.publishData(encoded, { reliable: true });
      } catch (e) {
        console.warn('[MediaService] Publish hand raise failed:', e);
      }
    }
  }

  /**
   * Broadcast floating emoji reaction to room.
   */
  sendReaction(emoji: string, localIdentity?: string) {
    const identity = this.getLocalIdentity(localIdentity);
    const localP = this.participantsMap.get(identity);
    if (localP) {
      localP.reaction = emoji;
      this.notifyParticipants();
      setTimeout(() => {
        if (localP.reaction === emoji) {
          localP.reaction = null;
          this.notifyParticipants();
        }
      }, 4000);
    }

    const payload = {
      type: 'REACTION',
      senderId: identity,
      senderName: localP?.name || 'User',
      emoji,
    };

    if (this.livekitRoom?.localParticipant) {
      try {
        const encoded = new TextEncoder().encode(JSON.stringify(payload));
        this.livekitRoom.localParticipant.publishData(encoded, { reliable: false });
      } catch (e) {
        console.warn('[MediaService] Publish reaction failed:', e);
      }
    }
    this.notifyReaction(payload);
  }

  /**
   * Start screen sharing via navigator.mediaDevices.getDisplayMedia or LiveKit.
   */
  async startScreenShare(localIdentity?: string): Promise<MediaStreamTrack | null> {
    const identity = this.getLocalIdentity(localIdentity);
    try {
      if (this.livekitRoom?.localParticipant) {
        await this.livekitRoom.localParticipant.setScreenShareEnabled(true);
      }

      const screenStream = await navigator.mediaDevices.getDisplayMedia({
        video: true,
        audio: false,
      });

      const screenTrack = screenStream.getVideoTracks()[0];
      this.localScreenStream = screenStream;

      screenTrack.onended = () => {
        this.stopScreenShare(identity);
      };

      const localP = this.participantsMap.get(identity);
      if (localP) {
        localP.isScreenSharing = true;
        localP.screenTrack = screenTrack;
        this.notifyParticipants();
      }

      return screenTrack;
    } catch (err: any) {
      console.warn('[MediaService] Screen share cancelled or failed:', err?.name || err);
      return null;
    }
  }

  /**
   * Stop local screen sharing.
   */
  async stopScreenShare(localIdentity?: string): Promise<void> {
    const identity = this.getLocalIdentity(localIdentity);
    if (this.localScreenStream) {
      this.localScreenStream.getTracks().forEach((t) => t.stop());
      this.localScreenStream = null;
    }

    if (this.livekitRoom?.localParticipant) {
      try {
        await this.livekitRoom.localParticipant.setScreenShareEnabled(false);
      } catch (e) {
        console.error(e);
      }
    }

    const localP = this.participantsMap.get(identity);
    if (localP) {
      localP.isScreenSharing = false;
      localP.screenTrack = null;
      this.notifyParticipants();
    }
  }

  /**
   * Broadcast in-meeting chat message to connected participants.
   */
  async broadcastChatMessage(msgData: any) {
    if (this.livekitRoom?.localParticipant) {
      try {
        const payload = new TextEncoder().encode(JSON.stringify(msgData));
        await this.livekitRoom.localParticipant.publishData(payload, { reliable: true });
      } catch (e) {
        console.warn('[MediaService] LiveKit publishData failed:', e);
      }
    }
    this.notifyChatMessage(msgData);
  }

  /**
   * Toggle local microphone audio state.
   */
  async toggleAudio(
    enabled: boolean,
    localIdentity?: string
  ): Promise<{ success: boolean; track?: MediaStreamTrack | null; error?: string; errorCode?: string }> {
    const identity = this.getLocalIdentity(localIdentity);
    console.log('[MediaService] toggleAudio requested:', { enabled, identity });

    if (enabled) {
      let audioTrack = this.localStream?.getAudioTracks()[0] || null;

      if (!audioTrack || audioTrack.readyState !== 'live') {
        const micRes = await this.requestMicrophoneTrack(this.selectedMicId || undefined);
        if (!micRes.track) {
          return {
            success: false,
            error: micRes.errorMessage || 'Microphone access failed.',
            errorCode: micRes.errorCode || 'UNKNOWN',
          };
        }
        audioTrack = micRes.track;
      } else {
        audioTrack.enabled = true;
      }

      const localP = this.participantsMap.get(identity);
      if (localP) {
        localP.audioTrack = audioTrack;
        localP.isAudioEnabled = true;
        this.notifyParticipants();
      }

      if (this.livekitRoom?.localParticipant) {
        try {
          await this.livekitRoom.localParticipant.publishTrack(audioTrack);
        } catch (pubErr) {
          try {
            await this.livekitRoom.localParticipant.setMicrophoneEnabled(true);
          } catch (e) {}
        }
      }

      return { success: true, track: audioTrack };
    } else {
      if (this.localStream) {
        const audioTrack = this.localStream.getAudioTracks()[0];
        if (audioTrack) audioTrack.enabled = false;
      }

      const localP = this.participantsMap.get(identity);
      if (localP) {
        localP.isAudioEnabled = false;
        this.notifyParticipants();
      }

      if (this.livekitRoom?.localParticipant) {
        try {
          await this.livekitRoom.localParticipant.setMicrophoneEnabled(false);
        } catch (e) {}
      }

      return { success: true, track: null };
    }
  }

  /**
   * Toggle local camera video state in real-time meeting room.
   * If turning on and no track exists (e.g. joined audio-only), acquires track via getUserMedia({ video: true })
   * and publishes to SFU room / participants.
   * If turning off, unpublishes track and calls track.stop() to turn hardware camera LED off.
   */
  async toggleVideo(
    enabled: boolean,
    localIdentity?: string
  ): Promise<{ success: boolean; track?: MediaStreamTrack | null; error?: string; errorCode?: string }> {
    const identity = this.getLocalIdentity(localIdentity);
    console.log('[MediaService] toggleVideo requested:', { enabled, identity });

    if (enabled) {
      // 1. Check if an active live video track already exists
      let videoTrack = this.localStream?.getVideoTracks()[0] || null;

      if (!videoTrack || videoTrack.readyState !== 'live') {
        console.log('[MediaService] No active video track exists. Requesting camera track via getUserMedia...');
        const camRes = await this.requestCameraTrack(this.selectedCameraId || undefined);

        if (!camRes.track) {
          console.warn('[MediaService] Failed to acquire camera track:', camRes.errorCode, camRes.errorMessage);
          return {
            success: false,
            error: camRes.errorMessage || 'Camera access failed or permission denied.',
            errorCode: camRes.errorCode || 'UNKNOWN',
          };
        }

        videoTrack = camRes.track;
      } else {
        videoTrack.enabled = true;
      }

      console.log('[MediaService] Active camera track:', {
        label: videoTrack.label,
        readyState: videoTrack.readyState,
        enabled: videoTrack.enabled,
        muted: videoTrack.muted,
      });

      // Update local participant state so tile updates immediately
      const localP = this.participantsMap.get(identity);
      if (localP) {
        localP.videoTrack = videoTrack;
        localP.isVideoEnabled = true;
        this.notifyParticipants();
      }

      // Publish track to LiveKit SFU room if active
      if (this.livekitRoom?.localParticipant) {
        try {
          console.log('[MediaService] Publishing video track to LiveKit SFU room...');
          await this.livekitRoom.localParticipant.publishTrack(videoTrack);
          console.log('[MediaService] Video track successfully published to LiveKit SFU room.');
        } catch (pubErr) {
          console.warn('[MediaService] Direct publishTrack failed, using setCameraEnabled:', pubErr);
          try {
            await this.livekitRoom.localParticipant.setCameraEnabled(true);
          } catch (e) {
            console.error('[MediaService] setCameraEnabled(true) error:', e);
          }
        }
      }

      // Refresh device list to capture real device labels now that permission is granted
      this.getAvailableDevices()
        .then(() => {
          this.notifyDeviceChange();
        })
        .catch(() => {});

      return { success: true, track: videoTrack };
    } else {
      // User is stopping video
      console.log('[MediaService] Stopping camera track and unpublishing...');
      const videoTrack = this.localStream?.getVideoTracks()[0] || null;

      if (this.livekitRoom?.localParticipant) {
        try {
          if (videoTrack) {
            await this.livekitRoom.localParticipant.unpublishTrack(videoTrack);
            console.log('[MediaService] Unpublished video track from LiveKit SFU room.');
          }
        } catch (unpubErr) {
          try {
            await this.livekitRoom.localParticipant.setCameraEnabled(false);
          } catch (e) {}
        }
      }

      // Stop the hardware track so camera LED goes OFF
      if (videoTrack) {
        try {
          videoTrack.stop();
          this.localStream?.removeTrack(videoTrack);
        } catch (e) {
          console.warn('[MediaService] Error stopping video track:', e);
        }
      }

      // Update local participant state to show avatar again
      const localP = this.participantsMap.get(identity);
      if (localP) {
        localP.videoTrack = null;
        localP.isVideoEnabled = false;
        this.notifyParticipants();
      }

      return { success: true, track: null };
    }
  }

  /**
   * Update active participants list manually.
   */
  updateRemoteParticipants(participants: any[], localIdentity: string) {
    if (!Array.isArray(participants)) return;

    participants.forEach((p) => {
      const pIdentity = p.user_id || p.media_identity || p.id;
      if (pIdentity && pIdentity !== localIdentity) {
        const existing = this.participantsMap.get(pIdentity);
        this.participantsMap.set(pIdentity, {
          id: pIdentity,
          identity: pIdentity,
          name: p.name || 'Participant',
          role: p.role === 'host' ? 'host' : 'attendee',
          isLocal: false,
          isAudioEnabled: p.participant_status === 'JOINED',
          isVideoEnabled: existing ? existing.isVideoEnabled : false,
          isScreenSharing: existing ? existing.isScreenSharing : false,
          isSpeaking: existing ? existing.isSpeaking : false,
          isHandRaised: existing ? existing.isHandRaised : false,
          reaction: existing ? existing.reaction : null,
          audioTrack: existing ? existing.audioTrack : null,
          videoTrack: existing ? existing.videoTrack : null,
          screenTrack: existing ? existing.screenTrack : null,
          joinedAt: p.joined_at || new Date().toISOString(),
        });
      }
    });

    this.notifyParticipants();
  }

  /**
   * Clean up local media tracks, audio meters, and disconnect room.
   */
  disconnect() {
    this.releaseLocalStream();

    if (this.localScreenStream) {
      this.localScreenStream.getTracks().forEach((track) => track.stop());
      this.localScreenStream = null;
    }

    if (this.livekitRoom) {
      try {
        this.livekitRoom.disconnect();
      } catch (e) {
        console.error(e);
      }
      this.livekitRoom = null;
    }

    this.participantsMap.clear();
    this.notifyStatus('DISCONNECTED');
    this.notifyParticipants();
  }

  subscribeDeviceChange(callback: DeviceChangeCallback): () => void {
    this.onDeviceChangeCallbacks.add(callback);
    return () => this.onDeviceChangeCallbacks.delete(callback);
  }

  private notifyDeviceChange() {
    this.onDeviceChangeCallbacks.forEach((cb) => {
      try {
        cb();
      } catch (e) {
        console.warn('[MediaService] DeviceChange callback error:', e);
      }
    });
  }

  subscribeParticipants(callback: MediaEventCallback): () => void {
    this.onParticipantsChangedCallbacks.add(callback);
    callback(Array.from(this.participantsMap.values()));
    return () => this.onParticipantsChangedCallbacks.delete(callback);
  }

  subscribeStatus(callback: StatusEventCallback): () => void {
    this.onRoomStatusChangedCallbacks.add(callback);
    return () => this.onRoomStatusChangedCallbacks.delete(callback);
  }

  subscribeChatMessage(callback: ChatEventCallback): () => void {
    this.onChatMessageCallbacks.add(callback);
    return () => this.onChatMessageCallbacks.delete(callback);
  }

  subscribeReaction(callback: ReactionEventCallback): () => void {
    this.onReactionCallbacks.add(callback);
    return () => this.onReactionCallbacks.delete(callback);
  }

  private notifyParticipants() {
    const list = Array.from(this.participantsMap.values());
    this.onParticipantsChangedCallbacks.forEach((cb) => cb(list));
  }

  private notifyStatus(status: string) {
    this.onRoomStatusChangedCallbacks.forEach((cb) => cb(status));
  }

  private notifyChatMessage(msg: any) {
    this.onChatMessageCallbacks.forEach((cb) => cb(msg));
  }

  private notifyReaction(payload: any) {
    this.onReactionCallbacks.forEach((cb) => cb(payload));
  }
}

export const mediaService = new ConvoMindMediaService();
