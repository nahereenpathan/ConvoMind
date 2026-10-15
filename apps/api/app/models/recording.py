"""MeetingRecording model definition."""

import uuid
from typing import TYPE_CHECKING, Optional
from sqlalchemy import (
    BigInteger,
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
from app.models.enums import RecordingStatus

if TYPE_CHECKING:
    from app.models.meeting import Meeting
    from app.models.transcript import Transcript
    from app.models.user import User
    from app.models.workspace import Workspace


class MeetingRecording(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Uploaded audio/video recording artifact associated with a meeting."""

    __tablename__ = "meeting_recordings"
    __table_args__ = (
        Index("ix_meeting_recordings_workspace_created_at", "workspace_id", "created_at"),
        Index("ix_meeting_recordings_meeting_created_at", "meeting_id", "created_at"),
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
    uploaded_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    original_filename: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    storage_key: Mapped[str] = mapped_column(
        String(1000),
        unique=True,
        index=True,
        nullable=False,
    )
    file_size: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )
    mime_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    duration_seconds: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    status: Mapped[RecordingStatus] = mapped_column(
        SAEnum(
            RecordingStatus,
            name="recording_status",
            native_enum=False,
            length=20,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        default=RecordingStatus.UPLOADED,
        nullable=False,
        index=True,
    )
    checksum: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    @property
    def uploaded_by(self) -> Optional[uuid.UUID]:
        """Convenience property mapping to uploaded_by_id."""
        return self.uploaded_by_id

    # Relationships
    meeting: Mapped["Meeting"] = relationship(
        "Meeting",
        back_populates="recordings",
    )
    workspace: Mapped["Workspace"] = relationship(
        "Workspace",
        back_populates="recordings",
    )
    uploader: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[uploaded_by_id],
    )
    transcript: Mapped[Optional["Transcript"]] = relationship(
        "Transcript",
        back_populates="recording",
        uselist=False,
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<MeetingRecording id={self.id} meeting_id={self.meeting_id} status={self.status}>"
