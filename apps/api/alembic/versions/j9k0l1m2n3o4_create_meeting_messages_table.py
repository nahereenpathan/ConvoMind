"""create_meeting_messages_table

Revision ID: j9k0l1m2n3o4
Revises: 93057a478ba9
Create Date: 2026-09-19 15:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'j9k0l1m2n3o4'
down_revision: Union[str, None] = '93057a478ba9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'meeting_messages',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('meeting_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('sender_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('sender_name', sa.String(length=255), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['meeting_id'], ['meetings.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['sender_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_meeting_messages_meeting_id'), 'meeting_messages', ['meeting_id'], unique=False)
    op.create_index(op.f('ix_meeting_messages_sender_id'), 'meeting_messages', ['sender_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_meeting_messages_sender_id'), table_name='meeting_messages')
    op.drop_index(op.f('ix_meeting_messages_meeting_id'), table_name='meeting_messages')
    op.drop_table('meeting_messages')
