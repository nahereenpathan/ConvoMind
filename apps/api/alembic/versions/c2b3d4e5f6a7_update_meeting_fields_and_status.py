"""update_meeting_fields_and_status

Revision ID: c2b3d4e5f6a7
Revises: b1a2c3d4e5f6
Create Date: 2026-09-17 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c2b3d4e5f6a7'
down_revision: Union[str, None] = 'b1a2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Expand status length to accommodate IN_PROGRESS and CANCELLED
    op.alter_column(
        'meetings',
        'status',
        type_=sa.String(length=20),
        existing_type=sa.String(length=10),
        nullable=False,
    )

    # 2. Add new meeting fields
    op.add_column('meetings', sa.Column('meeting_type', sa.String(length=100), nullable=True))
    op.add_column('meetings', sa.Column('source_type', sa.String(length=50), nullable=True))
    op.add_column('meetings', sa.Column('recording_key', sa.String(length=500), nullable=True))
    op.add_column('meetings', sa.Column('scheduled_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('meetings', sa.Column('started_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('meetings', sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True))

    # 3. Create query performance indexes
    op.create_index(op.f('ix_meetings_scheduled_at'), 'meetings', ['scheduled_at'], unique=False)
    op.create_index('ix_meetings_workspace_created_at', 'meetings', ['workspace_id', 'created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_meetings_workspace_created_at', table_name='meetings')
    op.drop_index(op.f('ix_meetings_scheduled_at'), table_name='meetings')
    op.drop_column('meetings', 'ended_at')
    op.drop_column('meetings', 'started_at')
    op.drop_column('meetings', 'scheduled_at')
    op.drop_column('meetings', 'recording_key')
    op.drop_column('meetings', 'source_type')
    op.drop_column('meetings', 'meeting_type')
    op.alter_column(
        'meetings',
        'status',
        type_=sa.String(length=10),
        existing_type=sa.String(length=20),
        nullable=False,
    )
