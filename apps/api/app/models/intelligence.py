"""Meeting intelligence models: MeetingIntelligenceJob, MeetingSummary, ActionItem, Decision, and MeetingQuestion."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import (
    ActionItemStatus,
    IntelligenceStatus,
    PriorityLevel,
    QuestionStatus,
)

if TYPE_CHECKING:
    from app.models.meeting import Meeting, Speaker
    from app.models.transcript import TranscriptSegment
    from app.models.user import User
    from app.models.workspace import Workspace


class MeetingIntelligenceJob(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Asynchronous tracking job for AI meeting intelligence processing."""

    __tablename__ = "meeting_intelligence_jobs"

    meeting_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meetings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[IntelligenceStatus] = mapped_column(
        SAEnum(
            IntelligenceStatus,
            name="intelligence_status",
            native_enum=False,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        default=IntelligenceStatus.QUEUED,
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="mock",
    )
    model: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="mock-model",
    )
    prompt_version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="v1",
    )
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    processing_duration: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    token_usage: Mapped[Optional[dict]] = mapped_column(
        JSONB().with_variant(JSON, "sqlite"),
        nullable=True,
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    meeting: Mapped["Meeting"] = relationship(
        "Meeting",
        back_populates="intelligence_jobs",
    )
    workspace: Mapped["Workspace"] = relationship(
        "Workspace",
    )

    def __repr__(self) -> str:
        return f"<MeetingIntelligenceJob id={self.id} meeting_id={self.meeting_id} status={self.status}>"


class MeetingSummary(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """AI-generated executive summary, detailed summary, key points, risks, and next steps."""

    __tablename__ = "meeting_summaries"

    meeting_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meetings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    overview: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    detailed_summary: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    key_points: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(
        JSONB().with_variant(JSON, "sqlite"),
        nullable=True,
    )
    next_steps: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(
        JSONB().with_variant(JSON, "sqlite"),
        nullable=True,
    )
    risks_and_concerns: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(
        JSONB().with_variant(JSON, "sqlite"),
        nullable=True,
    )
    requirements_and_notes: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(
        JSONB().with_variant(JSON, "sqlite"),
        nullable=True,
    )
    follow_up_suggestions: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(
        JSONB().with_variant(JSON, "sqlite"),
        nullable=True,
    )
    model_used: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    provider: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    prompt_version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="v1",
    )
    processing_duration: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    token_usage: Mapped[Optional[dict]] = mapped_column(
        JSONB().with_variant(JSON, "sqlite"),
        nullable=True,
    )
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        index=True,
    )
    job_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meeting_intelligence_jobs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Relationships
    meeting: Mapped["Meeting"] = relationship(
        "Meeting",
        back_populates="summaries",
    )
    workspace: Mapped["Workspace"] = relationship(
        "Workspace",
    )
    job: Mapped[Optional["MeetingIntelligenceJob"]] = relationship(
        "MeetingIntelligenceJob",
    )

    def __repr__(self) -> str:
        return f"<MeetingSummary id={self.id} meeting_id={self.meeting_id} version={self.version}>"


class ActionItem(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Extracted action item, task owner, due date, source segment reference, and fulfillment status."""

    __tablename__ = "action_items"
    __table_args__ = (
        Index("ix_action_items_workspace_status", "workspace_id", "status"),
        Index("ix_action_items_workspace_assignee", "workspace_id", "assignee_id"),
        Index("ix_action_items_due_date", "due_date"),
        Index("ix_action_items_meeting_status", "meeting_id", "status"),
    )

    meeting_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meetings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    assignee_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    assignee_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    due_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    status: Mapped[ActionItemStatus] = mapped_column(
        SAEnum(
            ActionItemStatus,
            name="action_item_status",
            native_enum=False,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        default=ActionItemStatus.OPEN,
        nullable=False,
        index=True,
    )
    priority: Mapped[PriorityLevel] = mapped_column(
        SAEnum(
            PriorityLevel,
            name="priority_level",
            native_enum=False,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        default=PriorityLevel.MEDIUM,
        nullable=False,
    )
    timestamp_marker: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    source_segment_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("transcript_segments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        index=True,
    )
    job_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meeting_intelligence_jobs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    updated_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    meeting: Mapped["Meeting"] = relationship(
        "Meeting",
        back_populates="action_items",
    )
    workspace: Mapped["Workspace"] = relationship(
        "Workspace",
    )
    assignee: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="assigned_action_items",
        foreign_keys=[assignee_id],
    )
    source_segment: Mapped[Optional["TranscriptSegment"]] = relationship(
        "TranscriptSegment",
    )
    job: Mapped[Optional["MeetingIntelligenceJob"]] = relationship(
        "MeetingIntelligenceJob",
    )
    created_by: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[created_by_id],
    )
    updated_by: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[updated_by_id],
    )

    def __repr__(self) -> str:
        return f"<ActionItem id={self.id} title={self.title} status={self.status} version={self.version}>"


class Decision(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Explicit decision or agreement logged during a meeting with source reference."""

    __tablename__ = "decisions"
    __table_args__ = (
        Index("ix_decisions_workspace_meeting", "workspace_id", "meeting_id"),
    )

    meeting_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meetings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    context: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    impact: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    timestamp_marker: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    source_segment_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("transcript_segments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        index=True,
    )
    job_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meeting_intelligence_jobs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    updated_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    meeting: Mapped["Meeting"] = relationship(
        "Meeting",
        back_populates="decisions",
    )
    workspace: Mapped["Workspace"] = relationship(
        "Workspace",
    )
    source_segment: Mapped[Optional["TranscriptSegment"]] = relationship(
        "TranscriptSegment",
    )
    job: Mapped[Optional["MeetingIntelligenceJob"]] = relationship(
        "MeetingIntelligenceJob",
    )
    created_by: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[created_by_id],
    )
    updated_by: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[updated_by_id],
    )

    def __repr__(self) -> str:
        return f"<Decision id={self.id} title={self.title} version={self.version}>"


class MeetingQuestion(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Question raised in the meeting, answers reached, and source reference."""

    __tablename__ = "meeting_questions"
    __table_args__ = (
        Index("ix_meeting_questions_workspace_status", "workspace_id", "status"),
        Index("ix_meeting_questions_meeting_status", "meeting_id", "status"),
    )

    meeting_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meetings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    asked_by_speaker_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("speakers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    asked_by_speaker_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    question: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    context: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    answer: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    status: Mapped[QuestionStatus] = mapped_column(
        SAEnum(
            QuestionStatus,
            name="question_status",
            native_enum=False,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        default=QuestionStatus.OPEN,
        nullable=False,
        index=True,
    )
    is_resolved: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    timestamp_marker: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    source_segment_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("transcript_segments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        index=True,
    )
    job_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meeting_intelligence_jobs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    updated_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    meeting: Mapped["Meeting"] = relationship(
        "Meeting",
        back_populates="questions",
    )
    workspace: Mapped["Workspace"] = relationship(
        "Workspace",
    )
    asked_by_speaker: Mapped[Optional["Speaker"]] = relationship(
        "Speaker",
        back_populates="questions",
        foreign_keys=[asked_by_speaker_id],
    )
    source_segment: Mapped[Optional["TranscriptSegment"]] = relationship(
        "TranscriptSegment",
    )
    job: Mapped[Optional["MeetingIntelligenceJob"]] = relationship(
        "MeetingIntelligenceJob",
    )
    created_by: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[created_by_id],
    )
    updated_by: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[updated_by_id],
    )

    def __repr__(self) -> str:
        return f"<MeetingQuestion id={self.id} question={self.question[:30]} status={self.status} version={self.version}>"

