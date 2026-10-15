"""create_chat_tables

Revision ID: h7g8f9e0d1c2
Revises: g6f7e8d9c0a1
Create Date: 2026-09-17 21:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSON

# revision identifiers, used by Alembic.
revision: str = 'h7g8f9e0d1c2'
down_revision: Union[str, None] = 'g6f7e8d9c0a1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create chat_conversations table
    op.create_table(
        'chat_conversations',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('workspace_id', UUID(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('meeting_id', UUID(as_uuid=True), sa.ForeignKey('meetings.id', ondelete='CASCADE'), nullable=True),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index(op.f('ix_chat_conversations_workspace_id'), 'chat_conversations', ['workspace_id'], unique=False)
    op.create_index(op.f('ix_chat_conversations_user_id'), 'chat_conversations', ['user_id'], unique=False)
    op.create_index(op.f('ix_chat_conversations_meeting_id'), 'chat_conversations', ['meeting_id'], unique=False)
    op.create_index('ix_chat_conversations_workspace_user', 'chat_conversations', ['workspace_id', 'user_id'], unique=False)
    op.create_index('ix_chat_conversations_workspace_meeting', 'chat_conversations', ['workspace_id', 'meeting_id'], unique=False)

    # 2. Create chat_messages table
    op.create_table(
        'chat_messages',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('conversation_id', UUID(as_uuid=True), sa.ForeignKey('chat_conversations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('sources', JSON(), nullable=True),
        sa.Column('tokens_used', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index(op.f('ix_chat_messages_conversation_id'), 'chat_messages', ['conversation_id'], unique=False)
    op.create_index('ix_chat_messages_conversation_created', 'chat_messages', ['conversation_id', 'created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_chat_messages_conversation_created', table_name='chat_messages')
    op.drop_index(op.f('ix_chat_messages_conversation_id'), table_name='chat_messages')
    op.drop_table('chat_messages')

    op.drop_index('ix_chat_conversations_workspace_meeting', table_name='chat_conversations')
    op.drop_index('ix_chat_conversations_workspace_user', table_name='chat_conversations')
    op.drop_index(op.f('ix_chat_conversations_meeting_id'), table_name='chat_conversations')
    op.drop_index(op.f('ix_chat_conversations_user_id'), table_name='chat_conversations')
    op.drop_index(op.f('ix_chat_conversations_workspace_id'), table_name='chat_conversations')
    op.drop_table('chat_conversations')
