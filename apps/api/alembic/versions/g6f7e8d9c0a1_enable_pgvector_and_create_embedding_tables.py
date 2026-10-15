"""enable_pgvector_and_create_embedding_tables

Revision ID: g6f7e8d9c0a1
Revises: a1b2c3d4e5f6
Create Date: 2026-09-17 21:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSON
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = 'g6f7e8d9c0a1'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Safely enable vector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # 2. Create transcript_embeddings table
    op.create_table(
        'transcript_embeddings',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('workspace_id', UUID(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('meeting_id', UUID(as_uuid=True), sa.ForeignKey('meetings.id', ondelete='CASCADE'), nullable=False),
        sa.Column('transcript_id', UUID(as_uuid=True), sa.ForeignKey('transcripts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('start_segment_id', UUID(as_uuid=True), sa.ForeignKey('transcript_segments.id', ondelete='SET NULL'), nullable=True),
        sa.Column('end_segment_id', UUID(as_uuid=True), sa.ForeignKey('transcript_segments.id', ondelete='SET NULL'), nullable=True),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('content_hash', sa.String(length=64), nullable=False),
        sa.Column('embedding', Vector(1536), nullable=False),
        sa.Column('provider', sa.String(length=50), nullable=False),
        sa.Column('model', sa.String(length=100), nullable=False),
        sa.Column('dimension', sa.Integer(), nullable=False),
        sa.Column('start_time', sa.Float(), nullable=True),
        sa.Column('end_time', sa.Float(), nullable=True),
        sa.Column('token_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('chunk_metadata', JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.UniqueConstraint('transcript_id', 'chunk_index', name='uq_transcript_chunk_index'),
    )

    # 3. Create standard B-tree indexes
    op.create_index(op.f('ix_transcript_embeddings_workspace_id'), 'transcript_embeddings', ['workspace_id'], unique=False)
    op.create_index(op.f('ix_transcript_embeddings_meeting_id'), 'transcript_embeddings', ['meeting_id'], unique=False)
    op.create_index(op.f('ix_transcript_embeddings_transcript_id'), 'transcript_embeddings', ['transcript_id'], unique=False)
    op.create_index(op.f('ix_transcript_embeddings_start_segment_id'), 'transcript_embeddings', ['start_segment_id'], unique=False)
    op.create_index(op.f('ix_transcript_embeddings_end_segment_id'), 'transcript_embeddings', ['end_segment_id'], unique=False)
    op.create_index('ix_transcript_embeddings_workspace_meeting', 'transcript_embeddings', ['workspace_id', 'meeting_id'], unique=False)
    op.create_index('ix_transcript_embeddings_transcript_chunk', 'transcript_embeddings', ['transcript_id', 'chunk_index'], unique=False)

    # 4. Create HNSW vector index using cosine distance
    op.execute(
        "CREATE INDEX ix_transcript_embeddings_hnsw ON transcript_embeddings "
        "USING hnsw (embedding vector_cosine_ops);"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_transcript_embeddings_hnsw;")
    op.drop_index('ix_transcript_embeddings_transcript_chunk', table_name='transcript_embeddings')
    op.drop_index('ix_transcript_embeddings_workspace_meeting', table_name='transcript_embeddings')
    op.drop_index(op.f('ix_transcript_embeddings_end_segment_id'), table_name='transcript_embeddings')
    op.drop_index(op.f('ix_transcript_embeddings_start_segment_id'), table_name='transcript_embeddings')
    op.drop_index(op.f('ix_transcript_embeddings_transcript_id'), table_name='transcript_embeddings')
    op.drop_index(op.f('ix_transcript_embeddings_meeting_id'), table_name='transcript_embeddings')
    op.drop_index(op.f('ix_transcript_embeddings_workspace_id'), table_name='transcript_embeddings')
    op.drop_table('transcript_embeddings')
