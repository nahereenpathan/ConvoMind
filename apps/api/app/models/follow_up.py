"""FollowUp model definition for AI-generated follow-up items and human approval workflow."""

import uuid
from typing import TYPE_CHECKING, Optional
from sqlalchemy import (
    Enum as SAEnum,
    ForeignKey,
    Index,
    JSON,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import FollowUpStatus, FollowUpType

if TYPE_CHECKING:
    from app.models.meeting import Meeting
    from app.models.user import User
    from app.models.workspace import Workspace


class FollowUp(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """AI-generated follow-up email draft or reminder subject to human review and approval."""

    __tablename__ = "follow_ups"
    __table_args__ = (
        Index("ix_follow_ups_workspace_created", "workspace_id", "created_at"),
        Index("ix_follow_ups_meeting_created", "meeting_id", "created_at"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    meeting_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meetings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    type: Mapped[FollowUpType] = mapped_column(
        SAEnum(
            FollowUpType,
            name="follow_up_type",
            native_enum=False,
            length=50,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        default=FollowUpType.EMAIL_DRAFT,
        nullable=False,
        index=True,
    )
    status: Mapped[FollowUpStatus] = mapped_column(
        SAEnum(
            FollowUpStatus,
            name="follow_up_status",
            native_enum=False,
            length=50,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        default=FollowUpStatus.DRAFT,
        nullable=False,
        index=True,
    )

    subject: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    recipients: Mapped[Optional[dict]] = mapped_column(
        JSONB().with_variant(JSON, "sqlite"),
        nullable=True,
    )
    follow_up_metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB().with_variant(JSON, "sqlite"),
        nullable=True,
    )

    # Relationships
    workspace: Mapped["Workspace"] = relationship("Workspace")
    meeting: Mapped["Meeting"] = relationship("Meeting")
    creator: Mapped[Optional["User"]] = relationship("User")

    def __repr__(self) -> str:
        return f"<FollowUp id={self.id} meeting_id={self.meeting_id} status={self.status}>"
