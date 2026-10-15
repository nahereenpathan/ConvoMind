"""EmailLog model for tracking email delivery, status, attempts, and idempotency."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional
from sqlalchemy import (
    DateTime,
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

if TYPE_CHECKING:
    from app.models.meeting import Meeting
    from app.models.user import User
    from app.models.workspace import Workspace


class EmailLog(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Audit log tracking outbound email messages, delivery status, retries, and errors."""

    __tablename__ = "email_logs"
    __table_args__ = (
        Index("ix_email_logs_recipient", "recipient_email"),
        Index("ix_email_logs_status", "status"),
        Index("ix_email_logs_idempotency", "idempotency_key", unique=True),
    )

    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    workspace_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    meeting_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meetings.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    recipient_email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    recipient_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    subject: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="QUEUED",
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(
        String(50),
        default="smtp",
        nullable=False,
    )
    attempts: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )
    idempotency_key: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    body_text: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    body_html: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    last_error: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    queued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    user: Mapped[Optional["User"]] = relationship("User")
    workspace: Mapped[Optional["Workspace"]] = relationship("Workspace")
    meeting: Mapped[Optional["Meeting"]] = relationship("Meeting")

    def __repr__(self) -> str:
        return f"<EmailLog id={self.id} recipient={self.recipient_email} event={self.event_type} status={self.status}>"
