"""User model definition."""

from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.intelligence import ActionItem
    from app.models.meeting import Meeting, MeetingParticipant, Speaker
    from app.models.refresh_token import RefreshToken
    from app.models.workspace import Workspace, WorkspaceMember


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """User account entity."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )
    hashed_password: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    full_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    avatar_url: Mapped[Optional[str]] = mapped_column(
        String(1024),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    is_superuser: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # Relationships
    workspace_memberships: Mapped[List["WorkspaceMember"]] = relationship(
        "WorkspaceMember",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    created_workspaces: Mapped[List["Workspace"]] = relationship(
        "Workspace",
        back_populates="creator",
        foreign_keys="Workspace.created_by_id",
    )
    created_meetings: Mapped[List["Meeting"]] = relationship(
        "Meeting",
        back_populates="creator",
        foreign_keys="Meeting.creator_id",
    )
    assigned_action_items: Mapped[List["ActionItem"]] = relationship(
        "ActionItem",
        back_populates="assignee",
        foreign_keys="ActionItem.assignee_id",
    )
    participations: Mapped[List["MeetingParticipant"]] = relationship(
        "MeetingParticipant",
        back_populates="user",
    )
    speakers: Mapped[List["Speaker"]] = relationship(
        "Speaker",
        back_populates="user",
    )
    refresh_tokens: Mapped[List["RefreshToken"]] = relationship(
        "RefreshToken",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email}>"
