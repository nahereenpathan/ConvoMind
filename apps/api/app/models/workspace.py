"""Workspace and WorkspaceMember model definitions."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import WorkspaceRole

if TYPE_CHECKING:
    from app.models.meeting import Meeting
    from app.models.recording import MeetingRecording
    from app.models.user import User



class Workspace(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Workspace entity representing an organization or team container."""

    __tablename__ = "workspaces"

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    slug: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
        nullable=False,
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    logo_url: Mapped[Optional[str]] = mapped_column(
        String(1024),
        nullable=True,
    )
    created_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Relationships
    creator: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="created_workspaces",
        foreign_keys=[created_by_id],
    )
    members: Mapped[List["WorkspaceMember"]] = relationship(
        "WorkspaceMember",
        back_populates="workspace",
        cascade="all, delete-orphan",
    )
    meetings: Mapped[List["Meeting"]] = relationship(
        "Meeting",
        back_populates="workspace",
        cascade="all, delete-orphan",
    )
    recordings: Mapped[List["MeetingRecording"]] = relationship(
        "MeetingRecording",
        back_populates="workspace",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Workspace id={self.id} slug={self.slug}>"


class WorkspaceMember(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Membership association between users and workspaces with role-based access."""

    __tablename__ = "workspace_members"
    __table_args__ = (
        UniqueConstraint("workspace_id", "user_id", name="uq_workspace_member"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[WorkspaceRole] = mapped_column(
        SAEnum(
            WorkspaceRole,
            name="workspace_role",
            native_enum=False,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        default=WorkspaceRole.MEMBER,
        nullable=False,
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    workspace: Mapped["Workspace"] = relationship(
        "Workspace",
        back_populates="members",
    )
    user: Mapped["User"] = relationship(
        "User",
        back_populates="workspace_memberships",
    )

    def __repr__(self) -> str:
        return f"<WorkspaceMember workspace_id={self.workspace_id} user_id={self.user_id} role={self.role}>"
