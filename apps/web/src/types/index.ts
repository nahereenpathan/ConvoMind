// Centralized TypeScript interface definitions for ConvoMind Frontend API contracts

export enum UserRole {
  OWNER = 'OWNER',
  ADMIN = 'ADMIN',
  MEMBER = 'MEMBER',
  GUEST = 'GUEST',
}

export enum MeetingStatus {
  SCHEDULED = 'SCHEDULED',
  IN_PROGRESS = 'IN_PROGRESS',
  RECORDING = 'RECORDING',
  PROCESSING = 'PROCESSING',
  COMPLETED = 'COMPLETED',
  FAILED = 'FAILED',
  CANCELLED = 'CANCELLED',
}

export enum RecordingStatus {
  UPLOADED = 'UPLOADED',
  QUEUED = 'QUEUED',
  PROCESSING = 'PROCESSING',
  COMPLETED = 'COMPLETED',
  FAILED = 'FAILED',
}

export enum MeetingPlatform {
  NATIVE = 'NATIVE',
  ZOOM = 'ZOOM',
  GOOGLE_MEET = 'GOOGLE_MEET',
  MS_TEAMS = 'MS_TEAMS',
  UPLOAD = 'UPLOAD',
  OTHER = 'OTHER',
}

export enum TranscriptStatus {
  PENDING = 'PENDING',
  PROCESSING = 'PROCESSING',
  COMPLETED = 'COMPLETED',
  FAILED = 'FAILED',
}

export enum ActionItemStatus {
  OPEN = 'OPEN',
  IN_PROGRESS = 'IN_PROGRESS',
  COMPLETED = 'COMPLETED',
  CANCELLED = 'CANCELLED',
}

export enum PriorityLevel {
  LOW = 'LOW',
  MEDIUM = 'MEDIUM',
  HIGH = 'HIGH',
  URGENT = 'URGENT',
}

export enum IntelligenceStatus {
  QUEUED = 'QUEUED',
  PROCESSING = 'PROCESSING',
  COMPLETED = 'COMPLETED',
  FAILED = 'FAILED',
}

export enum QuestionStatus {
  OPEN = 'OPEN',
  ANSWERED = 'ANSWERED',
  DISMISSED = 'DISMISSED',
}

export type NotificationType =
  | 'MEETING_PROCESSING_STARTED'
  | 'MEETING_PROCESSING_COMPLETED'
  | 'MEETING_PROCESSING_FAILED'
  | 'TRANSCRIPT_COMPLETED'
  | 'AI_ANALYSIS_COMPLETED'
  | 'AI_ANALYSIS_FAILED'
  | 'ACTION_ITEM_ASSIGNED'
  | 'ACTION_ITEM_UPDATED'
  | 'ACTION_ITEM_DUE_SOON'
  | 'ACTION_ITEM_OVERDUE'
  | 'DECISION_CREATED'
  | 'FOLLOW_UP_READY';

export type FollowUpType =
  | 'EMAIL_DRAFT'
  | 'ACTION_ITEM_REMINDER'
  | 'DECISION_CONFIRMATION'
  | 'CLIENT_FOLLOW_UP'
  | 'INTERNAL_FOLLOW_UP';

export type FollowUpStatus = 'DRAFT' | 'READY' | 'APPROVED' | 'SENT' | 'FAILED' | 'CANCELLED';

export interface User {
  id: string;
  email: string;
  full_name: string;
  avatar_url?: string;
  is_active: boolean;
  is_superuser: boolean;
  created_at: string;
  updated_at: string;
}

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface RegisterCredentials {
  email: string;
  password: string;
  name: string;
}

export interface AuthResponse {
  user: User;
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface Workspace {
  id: string;
  name: string;
  slug: string;
  description?: string;
  logo_url?: string;
  created_by_id: string;
  created_at: string;
  updated_at: string;
}

export interface WorkspaceMember {
  id: string;
  workspace_id: string;
  user_id: string;
  role: UserRole;
  user?: User;
  joined_at: string;
}

export interface Meeting {
  id: string;
  workspace_id: string;
  creator_id?: string;
  title: string;
  description?: string;
  status: MeetingStatus;
  platform?: MeetingPlatform;
  scheduled_at?: string;
  started_at?: string;
  ended_at?: string;
  duration_seconds?: number;
  is_native?: boolean;
  room_id?: string;
  room_provider?: string;
  room_status?: string;
  deleted_at?: string | null;
  deleted_by_id?: string | null;
  created_at: string;
  updated_at: string;
}

export interface MeetingListResponse {
  items: Meeting[];
  total: number;
  page: number;
  page_size: number;
}

export interface Recording {
  id: string;
  meeting_id: string;
  workspace_id: string;
  original_filename: string;
  storage_key: string;
  file_size: number;
  mime_type: string;
  duration_seconds?: number;
  status: RecordingStatus;
  error_message?: string;
  created_at: string;
}

export type MeetingRecording = Recording;

export interface SpeakerMap {
  id?: string;
  meeting_id?: string;
  speaker_label: string;
  display_name?: string;
  user_id?: string;
}

export type Speaker = SpeakerMap;

export interface TranscriptSegment {
  id: string;
  transcript_id?: string;
  sequence_order?: number;
  start_time: number;
  end_time: number;
  text: string;
  confidence?: number;
  speaker_id?: string;
  speaker_label?: string;
  created_at?: string;
  updated_at?: string;
}

export interface TranscriptWithSegmentsResponse {
  id: string;
  meeting_id: string;
  recording_id?: string;
  status: TranscriptStatus;
  language: string;
  full_text?: string;
  word_count: number;
  duration?: number;
  segments: TranscriptSegment[];
  created_at: string;
}

export interface MeetingSummary {
  id?: string;
  meeting_id?: string;
  overview: string;
  summary_text?: string;
  detailed_summary?: string;
  key_points?: Array<{ point?: string } | string>;
  next_steps?: Array<{ step?: string } | string>;
  risks_and_concerns?: Array<{ risk?: string } | string>;
  requirements_and_notes?: Array<{ note?: string } | string>;
  follow_up_suggestions?: Array<{ suggestion?: string } | string>;
  created_at?: string;
}

export interface ActionItem {
  id: string;
  workspace_id?: string;
  meeting_id?: string;
  meeting_title?: string;
  assignee_id?: string;
  assignee_name?: string;
  title: string;
  description?: string;
  status: ActionItemStatus;
  priority?: PriorityLevel;
  due_date?: string;
  timestamp_marker?: number;
  source_segment_id?: string;
  created_at?: string;
}

export interface Decision {
  id: string;
  workspace_id?: string;
  meeting_id?: string;
  title: string;
  description?: string;
  context?: string;
  impact?: string;
  timestamp_marker?: number;
  created_at?: string;
}

export interface MeetingQuestion {
  id: string;
  workspace_id?: string;
  meeting_id?: string;
  asked_by_speaker_name?: string;
  question: string;
  question_text?: string;
  answer?: string;
  status?: QuestionStatus;
  is_resolved?: boolean;
  timestamp_marker?: number;
  created_at?: string;
}

export interface IntelligenceJob {
  id: string;
  meeting_id: string;
  workspace_id: string;
  status: IntelligenceStatus;
  provider: string;
  model: string;
  version: number;
  error_message?: string;
  created_at: string;
}

export interface IntelligenceResult {
  meeting_id?: string;
  workspace_id?: string;
  version?: number;
  job?: IntelligenceJob;
  summary?: MeetingSummary;
  decisions: Decision[];
  action_items: ActionItem[];
  questions: MeetingQuestion[];
  status?: IntelligenceStatus;
}

export interface ChatConversation {
  id: string;
  workspace_id: string;
  meeting_id?: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface Citation {
  text?: string;
  text_excerpt?: string;
  speaker?: string;
  speaker_labels?: string[];
  score?: number;
  similarity_score?: number;
  start_time?: number;
  end_time?: number;
  meeting_title?: string;
}

export interface ChatMessage {
  id: string;
  conversation_id?: string;
  role: 'user' | 'assistant';
  content: string;
  citations?: Citation[];
  created_at?: string;
}

export interface ChatResponse {
  answer: string;
  citations: Citation[];
}

export interface AppNotification {
  id: string;
  user_id: string;
  workspace_id?: string;
  type: NotificationType;
  title: string;
  message: string;
  entity_type?: string;
  entity_id?: string;
  notification_metadata?: Record<string, any>;
  is_read: boolean;
  read_at?: string;
  created_at: string;
}

export type Notification = AppNotification;

export interface NotificationPreferences {
  id: string;
  user_id: string;
  email_enabled: boolean;
  in_app_enabled: boolean;
  notify_on_meeting_invitation: boolean;
  notify_on_meeting_reminder: boolean;
  notify_on_meeting_update: boolean;
  notify_on_meeting_cancellation: boolean;
  notify_on_meeting_complete: boolean;
  notify_on_ai_complete: boolean;
  notify_on_recording_ready: boolean;
  notify_on_action_item_assigned: boolean;
  notify_on_action_item_due: boolean;
  notify_on_follow_up_ready: boolean;
  created_at: string;
  updated_at: string;
}

export interface FollowUpEmail {
  id: string;
  workspace_id?: string;
  meeting_id: string;
  type?: FollowUpType;
  status: FollowUpStatus;
  subject: string;
  body: string;
  recipients?: string[];
  created_at?: string;
  updated_at?: string;
}

export type FollowUp = FollowUpEmail;

export type MeetingRoomState = 'PREJOIN' | 'CONNECTING' | 'CONNECTED' | 'RECONNECTING' | 'DISCONNECTED' | 'ENDED' | 'ERROR';

export interface MediaDeviceOption {
  deviceId: string;
  label: string;
}

export interface ParticipantTrackState {
  id: string;
  identity: string;
  name: string;
  role: 'host' | 'attendee';
  isLocal: boolean;
  isAudioEnabled: boolean;
  isVideoEnabled: boolean;
  isScreenSharing?: boolean;
  isSpeaking: boolean;
  isHandRaised?: boolean;
  reaction?: string | null;
  audioTrack?: MediaStreamTrack | null;
  videoTrack?: MediaStreamTrack | null;
  screenTrack?: MediaStreamTrack | null;
  joinedAt?: string;
}

export interface NativeRoomJoinData {
  meeting_id: string;
  room_id: string;
  ws_url: string;
  token: string;
  is_host: boolean;
  participant_identity: string;
  participant_name: string;
  room_status: string;
}

export interface MeetingChatMessage {
  id: string;
  meeting_id: string;
  sender_id?: string;
  sender_name: string;
  message: string;
  created_at: string;
}

export interface SubscriptionPlanResponse {
  id: string;
  code: string;
  name: string;
  description?: string;
  amount: number;
  currency: string;
  billing_interval: string;
  max_transcription_hours: number;
  max_rag_queries: number;
  max_members: number;
  active: boolean;
}

export interface WorkspaceSubscriptionResponse {
  id: string;
  workspace_id: string;
  plan_id: string;
  status: string;
  razorpay_subscription_id?: string;
  current_period_start?: string;
  current_period_end?: string;
  cancel_at_period_end: boolean;
  cancelled_at?: string;
  ended_at?: string;
  plan: SubscriptionPlanResponse;
}

export interface WorkspaceUsageResponse {
  transcribed_hours: number;
  max_transcription_hours: number;
  rag_queries: number;
  max_rag_queries: number;
  members_count: number;
  max_members: number;
  period_start?: string;
  period_end?: string;
  transcription_percentage: number;
  rag_percentage: number;
  members_percentage: number;
}

export interface CreateSubscriptionResponse {
  subscription_id: string;
  razorpay_subscription_id: string;
  razorpay_key_id: string;
  plan_code: string;
  plan_name: string;
  amount: number;
  currency: string;
  status: string;
}

export interface PaymentVerificationRequest {
  razorpay_payment_id: string;
  razorpay_subscription_id: string;
  razorpay_signature: string;
}

export interface PaymentTransactionResponse {
  id: string;
  razorpay_payment_id?: string;
  razorpay_subscription_id?: string;
  amount: number;
  currency: string;
  status: string;
  payment_method?: string;
  failure_reason?: string;
  paid_at?: string;
  created_at: string;
}



