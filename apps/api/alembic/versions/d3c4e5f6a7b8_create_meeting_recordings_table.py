"""create_meeting_recordings_table

Revision ID: d3c4e5f6a7b8
Revises: c2b3d4e5f6a7
Create Date: 2026-09-17 11:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd3c4e5f6a7b8'
down_revision: Union[str, None] = 'c2b3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'meeting_recordings',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('meeting_id', sa.UUID(), nullable=False),
        sa.Column('workspace_id', sa.UUID(), nullable=False),
        sa.Column('uploaded_by_id', sa.UUID(), nullable=True),
        sa.Column('original_filename', sa.String(length=500), nullable=False),
        sa.Column('storage_key', sa.String(length=1000), nullable=False),
        sa.Column('file_size', sa.BigInteger(), nullable=False),
        sa.Column('mime_type', sa.String(length=100), nullable=False),
        sa.Column('duration_seconds', sa.Integer(), nullable=True),
        sa.Column(
            'status',
            sa.Enum(
                'UPLOADED',
                'QUEUED',
                'PROCESSING',
                'COMPLETED',
                'FAILED',
                name='recording_status',
                native_enum=False,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column('checksum', sa.String(length=64), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['meeting_id'], ['meetings.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['uploaded_by_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_meeting_recordings_meeting_id'), 'meeting_recordings', ['meeting_id'], unique=False)
    op.create_index(op.f('ix_meeting_recordings_workspace_id'), 'meeting_recordings', ['workspace_id'], unique=False)
    op.create_index(op.f('ix_meeting_recordings_uploaded_by_id'), 'meeting_recordings', ['uploaded_by_id'], unique=False)
    op.create_index(op.f('ix_meeting_recordings_storage_key'), 'meeting_recordings', ['storage_key'], unique=True)
    op.create_index(op.f('ix_meeting_recordings_status'), 'meeting_recordings', ['status'], unique=False)
    op.create_index('ix_meeting_recordings_workspace_created_at', 'meeting_recordings', ['workspace_id', 'created_at'], unique=False)
    op.create_index('ix_meeting_recordings_meeting_created_at', 'meeting_recordings', ['meeting_id', 'created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_meeting_recordings_meeting_created_at', table_name='meeting_recordings')
    op.drop_index('ix_meeting_recordings_workspace_created_at', table_name='meeting_recordings')
    op.drop_index(op.f('ix_meeting_recordings_status'), table_name='meeting_recordings')
    op.drop_index(op.f('ix_meeting_recordings_storage_key'), table_name='meeting_recordings')
    op.drop_index(op.f('ix_meeting_recordings_uploaded_by_id'), table_name='meeting_recordings')
    op.drop_index(op.f('ix_meeting_recordings_workspace_id'), table_name='meeting_recordings')
    op.drop_index(op.f('ix_meeting_recordings_meeting_id'), table_name='meeting_recordings')
    op.drop_table('meeting_recordings')
