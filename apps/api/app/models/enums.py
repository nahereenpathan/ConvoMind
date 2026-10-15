"""Domain enumeration types for ConvoMind entities."""

from enum import Enum


class WorkspaceRole(str, Enum):
    """Roles for members within a workspace."""

    OWNER = "OWNER"
    ADMIN = "ADMIN"
    MEMBER = "MEMBER"
    GUEST = "GUEST"


class MeetingStatus(str, Enum):
    """Lifecycle states of a meeting."""

    SCHEDULED = "SCHEDULED"
    IN_PROGRESS = "IN_PROGRESS"
    RECORDING = "RECORDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class RecordingStatus(str, Enum):
    """Lifecycle states of a meeting recording."""

    UPLOADED = "UPLOADED"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class MeetingPlatform(str, Enum):
    """Source platform for meeting recordings."""

    NATIVE = "NATIVE"
    ZOOM = "ZOOM"
    GOOGLE_MEET = "GOOGLE_MEET"
    MS_TEAMS = "MS_TEAMS"
    UPLOAD = "UPLOAD"
    OTHER = "OTHER"


class TranscriptStatus(str, Enum):
    """Status of audio transcription and diarization pipeline."""

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ActionItemStatus(str, Enum):
    """Status of extracted meeting action items."""

    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class PriorityLevel(str, Enum):
    """Priority indicator for action items and tasks."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"


class IntelligenceStatus(str, Enum):
    """Lifecycle states of the AI meeting intelligence pipeline."""

    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class QuestionStatus(str, Enum):
    """Lifecycle states for questions extracted from meetings."""

    OPEN = "OPEN"
    ANSWERED = "ANSWERED"
    DISMISSED = "DISMISSED"


class NotificationType(str, Enum):
    """Types of user notifications."""

    MEETING_PROCESSING_STARTED = "MEETING_PROCESSING_STARTED"
    MEETING_PROCESSING_COMPLETED = "MEETING_PROCESSING_COMPLETED"
    MEETING_PROCESSING_FAILED = "MEETING_PROCESSING_FAILED"
    TRANSCRIPT_COMPLETED = "TRANSCRIPT_COMPLETED"
    AI_ANALYSIS_COMPLETED = "AI_ANALYSIS_COMPLETED"
    AI_ANALYSIS_FAILED = "AI_ANALYSIS_FAILED"
    ACTION_ITEM_ASSIGNED = "ACTION_ITEM_ASSIGNED"
    ACTION_ITEM_UPDATED = "ACTION_ITEM_UPDATED"
    ACTION_ITEM_DUE_SOON = "ACTION_ITEM_DUE_SOON"
    ACTION_ITEM_OVERDUE = "ACTION_ITEM_OVERDUE"
    DECISION_CREATED = "DECISION_CREATED"
    FOLLOW_UP_READY = "FOLLOW_UP_READY"
    PAYMENT_SUCCESSFUL = "PAYMENT_SUCCESSFUL"
    PAYMENT_FAILED = "PAYMENT_FAILED"
    SUBSCRIPTION_ACTIVATED = "SUBSCRIPTION_ACTIVATED"
    SUBSCRIPTION_CANCELLED = "SUBSCRIPTION_CANCELLED"
    QUOTA_WARNING = "QUOTA_WARNING"


class SubscriptionStatus(str, Enum):
    """Lifecycle states of a workspace subscription."""

    CREATED = "CREATED"
    AUTHENTICATION_PENDING = "AUTHENTICATION_PENDING"
    ACTIVE = "ACTIVE"
    PENDING = "PENDING"
    HALTED = "HALTED"
    CANCELLED = "CANCELLED"
    ENDED = "ENDED"


class PlanCode(str, Enum):
    """Subscription plan codes."""

    FREE = "FREE"
    PRO = "PRO"
    ENTERPRISE = "ENTERPRISE"


class FollowUpType(str, Enum):
    """Types of AI-generated meeting follow-ups."""

    EMAIL_DRAFT = "EMAIL_DRAFT"
    ACTION_ITEM_REMINDER = "ACTION_ITEM_REMINDER"
    DECISION_CONFIRMATION = "DECISION_CONFIRMATION"
    CLIENT_FOLLOW_UP = "CLIENT_FOLLOW_UP"
    INTERNAL_FOLLOW_UP = "INTERNAL_FOLLOW_UP"


class FollowUpStatus(str, Enum):
    """Lifecycle states of AI follow-up items."""

    DRAFT = "DRAFT"
    READY = "READY"
    APPROVED = "APPROVED"
    SENT = "SENT"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class EmailStatus(str, Enum):
    """Lifecycle states of an email log."""

    QUEUED = "QUEUED"
    SENDING = "SENDING"
    SENT = "SENT"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

