"""Notification and NotificationPreference model definitions."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional
from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import NotificationType

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.workspace import Workspace


class Notification(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """User notification entity for event-driven alerts."""

    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_user_unread", "user_id", "is_read", "created_at"),
        Index("ix_notifications_workspace_created", "workspace_id", "created_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type: Mapped[NotificationType] = mapped_column(
        SAEnum(
            NotificationType,
            name="notification_type",
            native_enum=False,
            length=50,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    entity_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )
    entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    notification_metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB().with_variant(JSON, "sqlite"),
        nullable=True,
    )
    is_read: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
    )
    read_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    user: Mapped["User"] = relationship("User")
    workspace: Mapped["Workspace"] = relationship("Workspace")

    def __repr__(self) -> str:
        return f"<Notification id={self.id} user_id={self.user_id} type={self.type} is_read={self.is_read}>"


class NotificationPreference(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """User notification settings and channel preferences."""

    __tablename__ = "notification_preferences"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_notification_preference_user"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    email_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    in_app_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    notify_on_meeting_invitation: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    notify_on_meeting_reminder: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    notify_on_meeting_update: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    notify_on_meeting_cancellation: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    notify_on_meeting_complete: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    notify_on_ai_complete: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    notify_on_recording_ready: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    notify_on_action_item_assigned: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    notify_on_action_item_due: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    notify_on_follow_up_ready: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship("User")

    def __repr__(self) -> str:
        return f"<NotificationPreference id={self.id} user_id={self.user_id}>"
