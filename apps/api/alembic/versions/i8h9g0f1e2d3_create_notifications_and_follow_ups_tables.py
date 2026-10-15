"""Create notifications, notification_preferences, and follow_ups tables.

Revision ID: i8h9g0f1e2d3
Revises: h7g8f9e0d1c2
Create Date: 2026-09-17 22:10:00.000000

"""
from alembic import op
import sqlalchemy as sqa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'i8h9g0f1e2d3'
down_revision = 'h7g8f9e0d1c2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create notifications table
    op.create_table(
        'notifications',
        sqa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sqa.Column('created_at', sqa.DateTime(timezone=True), server_default=sqa.text('now()'), nullable=False),
        sqa.Column('updated_at', sqa.DateTime(timezone=True), server_default=sqa.text('now()'), nullable=False),
        sqa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sqa.Column('workspace_id', postgresql.UUID(as_uuid=True), nullable=False),
        sqa.Column('type', sqa.String(length=50), nullable=False),
        sqa.Column('title', sqa.String(length=255), nullable=False),
        sqa.Column('message', sqa.Text(), nullable=False),
        sqa.Column('entity_type', sqa.String(length=100), nullable=True),
        sqa.Column('entity_id', postgresql.UUID(as_uuid=True), nullable=True),
        sqa.Column('notification_metadata', postgresql.JSONB(astext_type=sqa.Text()), nullable=True),
        sqa.Column('is_read', sqa.Boolean(), server_default=sqa.text('false'), nullable=False),
        sqa.Column('read_at', sqa.DateTime(timezone=True), nullable=True),
        sqa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sqa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sqa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_notifications_user_id', 'notifications', ['user_id'], unique=False)
    op.create_index('ix_notifications_workspace_id', 'notifications', ['workspace_id'], unique=False)
    op.create_index('ix_notifications_type', 'notifications', ['type'], unique=False)
    op.create_index('ix_notifications_entity_type', 'notifications', ['entity_type'], unique=False)
    op.create_index('ix_notifications_entity_id', 'notifications', ['entity_id'], unique=False)
    op.create_index('ix_notifications_is_read', 'notifications', ['is_read'], unique=False)
    op.create_index('ix_notifications_user_unread', 'notifications', ['user_id', 'is_read', 'created_at'], unique=False)
    op.create_index('ix_notifications_workspace_created', 'notifications', ['workspace_id', 'created_at'], unique=False)

    # 2. Create notification_preferences table
    op.create_table(
        'notification_preferences',
        sqa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sqa.Column('created_at', sqa.DateTime(timezone=True), server_default=sqa.text('now()'), nullable=False),
        sqa.Column('updated_at', sqa.DateTime(timezone=True), server_default=sqa.text('now()'), nullable=False),
        sqa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sqa.Column('email_enabled', sqa.Boolean(), server_default=sqa.text('true'), nullable=False),
        sqa.Column('in_app_enabled', sqa.Boolean(), server_default=sqa.text('true'), nullable=False),
        sqa.Column('notify_on_meeting_complete', sqa.Boolean(), server_default=sqa.text('true'), nullable=False),
        sqa.Column('notify_on_ai_complete', sqa.Boolean(), server_default=sqa.text('true'), nullable=False),
        sqa.Column('notify_on_action_item_assigned', sqa.Boolean(), server_default=sqa.text('true'), nullable=False),
        sqa.Column('notify_on_action_item_due', sqa.Boolean(), server_default=sqa.text('true'), nullable=False),
        sqa.Column('notify_on_follow_up_ready', sqa.Boolean(), server_default=sqa.text('true'), nullable=False),
        sqa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sqa.PrimaryKeyConstraint('id'),
        sqa.UniqueConstraint('user_id', name='uq_notification_preference_user')
    )
    op.create_index('ix_notification_preferences_user_id', 'notification_preferences', ['user_id'], unique=True)

    # 3. Create follow_ups table
    op.create_table(
        'follow_ups',
        sqa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sqa.Column('created_at', sqa.DateTime(timezone=True), server_default=sqa.text('now()'), nullable=False),
        sqa.Column('updated_at', sqa.DateTime(timezone=True), server_default=sqa.text('now()'), nullable=False),
        sqa.Column('workspace_id', postgresql.UUID(as_uuid=True), nullable=False),
        sqa.Column('meeting_id', postgresql.UUID(as_uuid=True), nullable=False),
        sqa.Column('created_by_id', postgresql.UUID(as_uuid=True), nullable=True),
        sqa.Column('type', sqa.String(length=50), nullable=False),
        sqa.Column('status', sqa.String(length=50), nullable=False),
        sqa.Column('subject', sqa.String(length=255), nullable=False),
        sqa.Column('content', sqa.Text(), nullable=False),
        sqa.Column('recipients', postgresql.JSONB(astext_type=sqa.Text()), nullable=True),
        sqa.Column('follow_up_metadata', postgresql.JSONB(astext_type=sqa.Text()), nullable=True),
        sqa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ondelete='SET NULL'),
        sqa.ForeignKeyConstraint(['meeting_id'], ['meetings.id'], ondelete='CASCADE'),
        sqa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sqa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_follow_ups_workspace_id', 'follow_ups', ['workspace_id'], unique=False)
    op.create_index('ix_follow_ups_meeting_id', 'follow_ups', ['meeting_id'], unique=False)
    op.create_index('ix_follow_ups_created_by_id', 'follow_ups', ['created_by_id'], unique=False)
    op.create_index('ix_follow_ups_type', 'follow_ups', ['type'], unique=False)
    op.create_index('ix_follow_ups_status', 'follow_ups', ['status'], unique=False)
    op.create_index('ix_follow_ups_workspace_created', 'follow_ups', ['workspace_id', 'created_at'], unique=False)
    op.create_index('ix_follow_ups_meeting_created', 'follow_ups', ['meeting_id', 'created_at'], unique=False)


def downgrade() -> None:
    op.drop_table('follow_ups')
    op.drop_table('notification_preferences')
    op.drop_table('notifications')
