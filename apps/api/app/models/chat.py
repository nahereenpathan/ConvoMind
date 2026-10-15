"""ChatConversation and ChatMessage model definitions for RAG AI Chat."""

import uuid
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.meeting import Meeting
    from app.models.user import User
    from app.models.workspace import Workspace


class ChatConversation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Chat conversation container for workspace or meeting-specific RAG dialogue."""

    __tablename__ = "chat_conversations"
    __table_args__ = (
        Index("ix_chat_conversations_workspace_user", "workspace_id", "user_id"),
        Index("ix_chat_conversations_workspace_meeting", "workspace_id", "meeting_id"),
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
    meeting_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meetings.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    # Relationships
    workspace: Mapped["Workspace"] = relationship("Workspace")
    user: Mapped["User"] = relationship("User")
    meeting: Mapped[Optional["Meeting"]] = relationship("Meeting")
    messages: Mapped[List["ChatMessage"]] = relationship(
        "ChatMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at",
    )

    def __repr__(self) -> str:
        return (
            f"<ChatConversation id={self.id} workspace_id={self.workspace_id} "
            f"user_id={self.user_id} title='{self.title}'>"
        )


class ChatMessage(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Individual message record within a chat conversation."""

    __tablename__ = "chat_messages"
    __table_args__ = (
        Index("ix_chat_messages_conversation_created", "conversation_id", "created_at"),
    )

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chat_conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    sources: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
    )
    tokens_used: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    # Relationships
    conversation: Mapped["ChatConversation"] = relationship(
        "ChatConversation",
        back_populates="messages",
    )

    def __repr__(self) -> str:
        return (
            f"<ChatMessage id={self.id} conversation_id={self.conversation_id} role={self.role}>"
        )
