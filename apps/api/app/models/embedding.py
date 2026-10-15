"""TranscriptEmbedding model for vector storage and semantic search via pgvector."""

import uuid
from typing import TYPE_CHECKING, Optional
from pgvector.sqlalchemy import Vector
from sqlalchemy import Float, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import settings
from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.meeting import Meeting
    from app.models.transcript import Transcript, TranscriptSegment
    from app.models.workspace import Workspace


class TranscriptEmbedding(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Vector embedding of a transcript text chunk with strict workspace isolation."""

    __tablename__ = "transcript_embeddings"
    __table_args__ = (
        Index("ix_transcript_embeddings_workspace_meeting", "workspace_id", "meeting_id"),
        Index("ix_transcript_embeddings_transcript_chunk", "transcript_id", "chunk_index"),
        Index(
            "ix_transcript_embeddings_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        UniqueConstraint("transcript_id", "chunk_index", name="uq_transcript_chunk_index"),
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
    transcript_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("transcripts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    start_segment_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("transcript_segments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    end_segment_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("transcript_segments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    chunk_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    content_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    embedding = mapped_column(
        Vector(settings.EMBEDDING_DIMENSION),
        nullable=False,
    )

    provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    model: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    dimension: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    start_time: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    end_time: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    token_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    chunk_metadata: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
    )

    # Relationships
    workspace: Mapped["Workspace"] = relationship("Workspace")
    meeting: Mapped["Meeting"] = relationship("Meeting")
    transcript: Mapped["Transcript"] = relationship("Transcript")
    start_segment: Mapped[Optional["TranscriptSegment"]] = relationship(
        "TranscriptSegment", foreign_keys=[start_segment_id]
    )
    end_segment: Mapped[Optional["TranscriptSegment"]] = relationship(
        "TranscriptSegment", foreign_keys=[end_segment_id]
    )

    def __repr__(self) -> str:
        return (
            f"<TranscriptEmbedding id={self.id} workspace_id={self.workspace_id} "
            f"meeting_id={self.meeting_id} chunk_index={self.chunk_index}>"
        )
