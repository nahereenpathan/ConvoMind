"""add_extended_notification_preferences

Revision ID: e73819fa991d
Revises: ca46ed07e3fd
Create Date: 2026-09-19 18:38:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'e73819fa991d'
down_revision: Union[str, None] = 'ca46ed07e3fd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('notification_preferences', sa.Column('notify_on_meeting_invitation', sa.Boolean(), server_default='true', nullable=False))
    op.add_column('notification_preferences', sa.Column('notify_on_meeting_reminder', sa.Boolean(), server_default='true', nullable=False))
    op.add_column('notification_preferences', sa.Column('notify_on_meeting_update', sa.Boolean(), server_default='true', nullable=False))
    op.add_column('notification_preferences', sa.Column('notify_on_meeting_cancellation', sa.Boolean(), server_default='true', nullable=False))
    op.add_column('notification_preferences', sa.Column('notify_on_recording_ready', sa.Boolean(), server_default='true', nullable=False))


def downgrade() -> None:
    op.drop_column('notification_preferences', 'notify_on_recording_ready')
    op.drop_column('notification_preferences', 'notify_on_meeting_cancellation')
    op.drop_column('notification_preferences', 'notify_on_meeting_update')
    op.drop_column('notification_preferences', 'notify_on_meeting_reminder')
    op.drop_column('notification_preferences', 'notify_on_meeting_invitation')
