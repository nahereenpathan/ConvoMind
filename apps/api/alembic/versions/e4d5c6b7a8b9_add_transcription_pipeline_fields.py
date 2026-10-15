"""add_transcription_pipeline_fields

Revision ID: e4d5c6b7a8b9
Revises: d3c4e5f6a7b8
Create Date: 2026-09-17 11:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e4d5c6b7a8b9'
down_revision: Union[str, None] = 'd3c4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add transcription metadata columns to transcripts table
    op.add_column('transcripts', sa.Column('recording_id', sa.UUID(), nullable=True))
    op.add_column('transcripts', sa.Column('workspace_id', sa.UUID(), nullable=True))
    op.add_column('transcripts', sa.Column('duration', sa.Float(), nullable=True))
    op.add_column('transcripts', sa.Column('provider', sa.String(length=100), nullable=True))
    op.add_column('transcripts', sa.Column('processing_metadata', sa.JSON(), nullable=True))
    op.add_column('transcripts', sa.Column('error_message', sa.Text(), nullable=True))

    # 2. Add foreign keys
    op.create_foreign_key(
        'fk_transcripts_recording_id',
        'transcripts',
        'meeting_recordings',
        ['recording_id'],
        ['id'],
        ondelete='CASCADE',
    )
    op.create_foreign_key(
        'fk_transcripts_workspace_id',
        'transcripts',
        'workspaces',
        ['workspace_id'],
        ['id'],
        ondelete='CASCADE',
    )

    # 3. Create indexes
    op.create_index(
        op.f('ix_transcripts_recording_id'),
        'transcripts',
        ['recording_id'],
        unique=True,
    )
    op.create_index(
        op.f('ix_transcripts_workspace_id'),
        'transcripts',
        ['workspace_id'],
        unique=False,
    )
    op.create_index(
        'ix_transcripts_workspace_created_at',
        'transcripts',
        ['workspace_id', 'created_at'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('ix_transcripts_workspace_created_at', table_name='transcripts')
    op.drop_index(op.f('ix_transcripts_workspace_id'), table_name='transcripts')
    op.drop_index(op.f('ix_transcripts_recording_id'), table_name='transcripts')
    op.drop_constraint('fk_transcripts_workspace_id', 'transcripts', type_='foreignkey')
    op.drop_constraint('fk_transcripts_recording_id', 'transcripts', type_='foreignkey')
    op.drop_column('transcripts', 'error_message')
    op.drop_column('transcripts', 'processing_metadata')
    op.drop_column('transcripts', 'provider')
    op.drop_column('transcripts', 'duration')
    op.drop_column('transcripts', 'workspace_id')
    op.drop_column('transcripts', 'recording_id')
