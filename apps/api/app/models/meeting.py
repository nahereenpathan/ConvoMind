"""Meeting, MeetingParticipant, and Speaker model definitions."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import MeetingPlatform, MeetingStatus

if TYPE_CHECKING:
    from app.models.intelligence import ActionItem, Decision, MeetingIntelligenceJob, MeetingQuestion, MeetingSummary
    from app.models.recording import MeetingRecording
    from app.models.transcript import Transcript, TranscriptSegment
    from app.models.user import User
    from app.models.workspace import Workspace



class Meeting(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Meeting entity representing an audio/video session and intelligence hub."""

    __tablename__ = "meetings"
    __table_args__ = (
        Index("ix_meetings_workspace_created_at", "workspace_id", "created_at"),
        Index("ix_meetings_workspace_deleted_at", "workspace_id", "deleted_at"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    creator_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    deleted_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    status: Mapped[MeetingStatus] = mapped_column(
        SAEnum(
            MeetingStatus,
            name="meeting_status",
            native_enum=False,
            length=20,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        default=MeetingStatus.SCHEDULED,
        nullable=False,
        index=True,
    )
    platform: Mapped[MeetingPlatform] = mapped_column(
        SAEnum(
            MeetingPlatform,
            name="meeting_platform",
            native_enum=False,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        default=MeetingPlatform.OTHER,
        nullable=False,
    )
    external_meeting_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )
    meeting_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    source_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    recording_url: Mapped[Optional[str]] = mapped_column(
        String(1024),
        nullable=True,
    )
    recording_key: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    scheduled_start_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    actual_start_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    actual_end_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    duration_seconds: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    is_native: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    room_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        unique=True,
        index=True,
    )
    room_provider: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        default="livekit",
    )
    room_status: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        default="IDLE",
    )

    @property
    def created_by(self) -> Optional[uuid.UUID]:
        """Convenience property mapping to creator_id."""
        return self.creator_id


    # Relationships
    workspace: Mapped["Workspace"] = relationship(
        "Workspace",
        back_populates="meetings",
    )
    creator: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="created_meetings",
        foreign_keys=[creator_id],
    )
    deleted_by: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[deleted_by_id],
    )
    recordings: Mapped[List["MeetingRecording"]] = relationship(
        "MeetingRecording",
        back_populates="meeting",
        cascade="all, delete-orphan",
    )
    participants: Mapped[List["MeetingParticipant"]] = relationship(
        "MeetingParticipant",
        back_populates="meeting",
        cascade="all, delete-orphan",
    )
    speakers: Mapped[List["Speaker"]] = relationship(
        "Speaker",
        back_populates="meeting",
        cascade="all, delete-orphan",
    )
    transcripts: Mapped[List["Transcript"]] = relationship(
        "Transcript",
        back_populates="meeting",
        cascade="all, delete-orphan",
    )
    summaries: Mapped[List["MeetingSummary"]] = relationship(
        "MeetingSummary",
        back_populates="meeting",
        cascade="all, delete-orphan",
    )
    action_items: Mapped[List["ActionItem"]] = relationship(
        "ActionItem",
        back_populates="meeting",
        cascade="all, delete-orphan",
    )
    decisions: Mapped[List["Decision"]] = relationship(
        "Decision",
        back_populates="meeting",
        cascade="all, delete-orphan",
    )
    questions: Mapped[List["MeetingQuestion"]] = relationship(
        "MeetingQuestion",
        back_populates="meeting",
        cascade="all, delete-orphan",
    )
    intelligence_jobs: Mapped[List["MeetingIntelligenceJob"]] = relationship(
        "MeetingIntelligenceJob",
        back_populates="meeting",
        cascade="all, delete-orphan",
    )
    messages: Mapped[List["MeetingMessage"]] = relationship(
        "MeetingMessage",
        back_populates="meeting",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Meeting id={self.id} title={self.title} status={self.status}>"


class MeetingParticipant(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Participant attending a meeting."""

    __tablename__ = "meeting_participants"

    meeting_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meetings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    email: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    role: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    joined_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    left_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    participant_status: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        default="INVITED",
    )
    media_identity: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )

    # Relationships
    meeting: Mapped["Meeting"] = relationship(
        "Meeting",
        back_populates="participants",
    )
    user: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="participations",
    )

    def __repr__(self) -> str:
        return f"<MeetingParticipant id={self.id} meeting_id={self.meeting_id} name={self.name}>"


class Speaker(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Identified speaker in meeting audio for diarization."""

    __tablename__ = "speakers"

    meeting_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meetings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    label: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    # Relationships
    meeting: Mapped["Meeting"] = relationship(
        "Meeting",
        back_populates="speakers",
    )
    user: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="speakers",
    )
    segments: Mapped[List["TranscriptSegment"]] = relationship(
        "TranscriptSegment",
        back_populates="speaker",
    )
    questions: Mapped[List["MeetingQuestion"]] = relationship(
        "MeetingQuestion",
        back_populates="asked_by_speaker",
    )

    def __repr__(self) -> str:
        return f"<Speaker id={self.id} label={self.label} name={self.name}>"


class MeetingMessage(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """In-meeting chat message entity."""

    __tablename__ = "meeting_messages"

    meeting_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meetings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sender_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    sender_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # Relationships
    meeting: Mapped["Meeting"] = relationship(
        "Meeting",
        back_populates="messages",
    )
    sender: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[sender_id],
    )

    def __repr__(self) -> str:
        return f"<MeetingMessage id={self.id} meeting_id={self.meeting_id} sender_name={self.sender_name}>"

