"""Transcript and TranscriptSegment model definitions."""

import uuid
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import (
    Enum as SAEnum,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import TranscriptStatus

if TYPE_CHECKING:
    from app.models.meeting import Meeting, Speaker
    from app.models.recording import MeetingRecording
    from app.models.workspace import Workspace


class Transcript(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Transcript entity containing text and diarized segments for a meeting."""

    __tablename__ = "transcripts"
    __table_args__ = (
        Index("ix_transcripts_workspace_created_at", "workspace_id", "created_at"),
    )

    meeting_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meetings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    recording_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meeting_recordings.id", ondelete="CASCADE"),
        nullable=True,
        unique=True,
        index=True,
    )
    workspace_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    language: Mapped[str] = mapped_column(
        String(50),
        default="en",
        nullable=False,
    )
    status: Mapped[TranscriptStatus] = mapped_column(
        SAEnum(
            TranscriptStatus,
            name="transcript_status",
            native_enum=False,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        default=TranscriptStatus.PENDING,
        nullable=False,
        index=True,
    )
    full_text: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    word_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    confidence_score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    duration: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    provider: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    processing_metadata: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    meeting: Mapped["Meeting"] = relationship(
        "Meeting",
        back_populates="transcripts",
    )
    recording: Mapped[Optional["MeetingRecording"]] = relationship(
        "MeetingRecording",
        back_populates="transcript",
    )
    workspace: Mapped[Optional["Workspace"]] = relationship(
        "Workspace",
    )
    segments: Mapped[List["TranscriptSegment"]] = relationship(
        "TranscriptSegment",
        back_populates="transcript",
        cascade="all, delete-orphan",
        order_by="TranscriptSegment.sequence_order",
    )

    def __repr__(self) -> str:
        return f"<Transcript id={self.id} meeting_id={self.meeting_id} status={self.status}>"


class TranscriptSegment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Individual segment of spoken dialogue with timestamp and speaker tagging."""

    __tablename__ = "transcript_segments"
    __table_args__ = (
        UniqueConstraint(
            "transcript_id", "sequence_order", name="uq_transcript_segment_order"
        ),
        Index("ix_transcript_segment_time", "transcript_id", "start_time", "end_time"),
    )

    transcript_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("transcripts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    speaker_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("speakers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    sequence_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
    )
    start_time: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    end_time: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    confidence: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    # Embedding reference or external vector ID ready for pgvector integration
    embedding_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )

    # Relationships
    transcript: Mapped["Transcript"] = relationship(
        "Transcript",
        back_populates="segments",
    )
    speaker: Mapped[Optional["Speaker"]] = relationship(
        "Speaker",
        back_populates="segments",
    )

    def __repr__(self) -> str:
        return f"<TranscriptSegment id={self.id} transcript_id={self.transcript_id} order={self.sequence_order}>"
