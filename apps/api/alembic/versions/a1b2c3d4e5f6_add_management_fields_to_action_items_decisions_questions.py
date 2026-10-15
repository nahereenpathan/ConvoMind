"""add_management_fields_to_action_items_decisions_questions

Revision ID: a1b2c3d4e5f6
Revises: f5e6d7c8b9a0
Create Date: 2026-09-17 12:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'f5e6d7c8b9a0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # =========================================================================
    # 1. action_items
    # =========================================================================
    op.add_column('action_items', sa.Column('workspace_id', sa.UUID(), nullable=True))
    op.execute(
        "UPDATE action_items SET workspace_id = meetings.workspace_id "
        "FROM meetings WHERE action_items.meeting_id = meetings.id"
    )
    op.alter_column('action_items', 'workspace_id', nullable=False)
    op.create_foreign_key(
        'fk_action_items_workspace_id',
        'action_items',
        'workspaces',
        ['workspace_id'],
        ['id'],
        ondelete='CASCADE',
    )
    op.add_column('action_items', sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('action_items', sa.Column('created_by_id', sa.UUID(), nullable=True))
    op.add_column('action_items', sa.Column('updated_by_id', sa.UUID(), nullable=True))
    op.create_foreign_key(
        'fk_action_items_created_by_id',
        'action_items',
        'users',
        ['created_by_id'],
        ['id'],
        ondelete='SET NULL',
    )
    op.create_foreign_key(
        'fk_action_items_updated_by_id',
        'action_items',
        'users',
        ['updated_by_id'],
        ['id'],
        ondelete='SET NULL',
    )
    op.create_index(op.f('ix_action_items_workspace_id'), 'action_items', ['workspace_id'], unique=False)
    op.create_index(op.f('ix_action_items_created_by_id'), 'action_items', ['created_by_id'], unique=False)
    op.create_index('ix_action_items_workspace_status', 'action_items', ['workspace_id', 'status'], unique=False)
    op.create_index('ix_action_items_workspace_assignee', 'action_items', ['workspace_id', 'assignee_id'], unique=False)
    op.create_index('ix_action_items_due_date', 'action_items', ['due_date'], unique=False)
    op.create_index('ix_action_items_meeting_status', 'action_items', ['meeting_id', 'status'], unique=False)

    # =========================================================================
    # 2. decisions
    # =========================================================================
    op.add_column('decisions', sa.Column('workspace_id', sa.UUID(), nullable=True))
    op.execute(
        "UPDATE decisions SET workspace_id = meetings.workspace_id "
        "FROM meetings WHERE decisions.meeting_id = meetings.id"
    )
    op.alter_column('decisions', 'workspace_id', nullable=False)
    op.create_foreign_key(
        'fk_decisions_workspace_id',
        'decisions',
        'workspaces',
        ['workspace_id'],
        ['id'],
        ondelete='CASCADE',
    )
    op.add_column('decisions', sa.Column('created_by_id', sa.UUID(), nullable=True))
    op.add_column('decisions', sa.Column('updated_by_id', sa.UUID(), nullable=True))
    op.create_foreign_key(
        'fk_decisions_created_by_id',
        'decisions',
        'users',
        ['created_by_id'],
        ['id'],
        ondelete='SET NULL',
    )
    op.create_foreign_key(
        'fk_decisions_updated_by_id',
        'decisions',
        'users',
        ['updated_by_id'],
        ['id'],
        ondelete='SET NULL',
    )
    op.create_index(op.f('ix_decisions_workspace_id'), 'decisions', ['workspace_id'], unique=False)
    op.create_index(op.f('ix_decisions_created_by_id'), 'decisions', ['created_by_id'], unique=False)
    op.create_index('ix_decisions_workspace_meeting', 'decisions', ['workspace_id', 'meeting_id'], unique=False)

    # =========================================================================
    # 3. meeting_questions
    # =========================================================================
    op.add_column('meeting_questions', sa.Column('workspace_id', sa.UUID(), nullable=True))
    op.execute(
        "UPDATE meeting_questions SET workspace_id = meetings.workspace_id "
        "FROM meetings WHERE meeting_questions.meeting_id = meetings.id"
    )
    op.alter_column('meeting_questions', 'workspace_id', nullable=False)
    op.create_foreign_key(
        'fk_meeting_questions_workspace_id',
        'meeting_questions',
        'workspaces',
        ['workspace_id'],
        ['id'],
        ondelete='CASCADE',
    )
    op.add_column('meeting_questions', sa.Column('context', sa.Text(), nullable=True))
    op.add_column(
        'meeting_questions',
        sa.Column(
            'status',
            sa.Enum('OPEN', 'ANSWERED', 'DISMISSED', name='question_status', native_enum=False),
            nullable=False,
            server_default='OPEN',
        ),
    )
    op.execute("UPDATE meeting_questions SET status = 'ANSWERED' WHERE is_resolved = true")
    op.add_column('meeting_questions', sa.Column('created_by_id', sa.UUID(), nullable=True))
    op.add_column('meeting_questions', sa.Column('updated_by_id', sa.UUID(), nullable=True))
    op.create_foreign_key(
        'fk_meeting_questions_created_by_id',
        'meeting_questions',
        'users',
        ['created_by_id'],
        ['id'],
        ondelete='SET NULL',
    )
    op.create_foreign_key(
        'fk_meeting_questions_updated_by_id',
        'meeting_questions',
        'users',
        ['updated_by_id'],
        ['id'],
        ondelete='SET NULL',
    )
    op.create_index(op.f('ix_meeting_questions_workspace_id'), 'meeting_questions', ['workspace_id'], unique=False)
    op.create_index(op.f('ix_meeting_questions_status'), 'meeting_questions', ['status'], unique=False)
    op.create_index(op.f('ix_meeting_questions_created_by_id'), 'meeting_questions', ['created_by_id'], unique=False)
    op.create_index('ix_meeting_questions_workspace_status', 'meeting_questions', ['workspace_id', 'status'], unique=False)
    op.create_index('ix_meeting_questions_meeting_status', 'meeting_questions', ['meeting_id', 'status'], unique=False)


def downgrade() -> None:
    # 3. meeting_questions
    op.drop_index('ix_meeting_questions_meeting_status', table_name='meeting_questions')
    op.drop_index('ix_meeting_questions_workspace_status', table_name='meeting_questions')
    op.drop_index(op.f('ix_meeting_questions_created_by_id'), table_name='meeting_questions')
    op.drop_index(op.f('ix_meeting_questions_status'), table_name='meeting_questions')
    op.drop_index(op.f('ix_meeting_questions_workspace_id'), table_name='meeting_questions')
    op.drop_constraint('fk_meeting_questions_updated_by_id', 'meeting_questions', type_='foreignkey')
    op.drop_constraint('fk_meeting_questions_created_by_id', 'meeting_questions', type_='foreignkey')
    op.drop_column('meeting_questions', 'updated_by_id')
    op.drop_column('meeting_questions', 'created_by_id')
    op.drop_column('meeting_questions', 'status')
    op.drop_column('meeting_questions', 'context')
    op.drop_constraint('fk_meeting_questions_workspace_id', 'meeting_questions', type_='foreignkey')
    op.drop_column('meeting_questions', 'workspace_id')

    # 2. decisions
    op.drop_index('ix_decisions_workspace_meeting', table_name='decisions')
    op.drop_index(op.f('ix_decisions_created_by_id'), table_name='decisions')
    op.drop_index(op.f('ix_decisions_workspace_id'), table_name='decisions')
    op.drop_constraint('fk_decisions_updated_by_id', 'decisions', type_='foreignkey')
    op.drop_constraint('fk_decisions_created_by_id', 'decisions', type_='foreignkey')
    op.drop_column('decisions', 'updated_by_id')
    op.drop_column('decisions', 'created_by_id')
    op.drop_constraint('fk_decisions_workspace_id', 'decisions', type_='foreignkey')
    op.drop_column('decisions', 'workspace_id')

    # 1. action_items
    op.drop_index('ix_action_items_meeting_status', table_name='action_items')
    op.drop_index('ix_action_items_due_date', table_name='action_items')
    op.drop_index('ix_action_items_workspace_assignee', table_name='action_items')
    op.drop_index('ix_action_items_workspace_status', table_name='action_items')
    op.drop_index(op.f('ix_action_items_created_by_id'), table_name='action_items')
    op.drop_index(op.f('ix_action_items_workspace_id'), table_name='action_items')
    op.drop_constraint('fk_action_items_updated_by_id', 'action_items', type_='foreignkey')
    op.drop_constraint('fk_action_items_created_by_id', 'action_items', type_='foreignkey')
    op.drop_column('action_items', 'updated_by_id')
    op.drop_column('action_items', 'created_by_id')
    op.drop_column('action_items', 'completed_at')
    op.drop_constraint('fk_action_items_workspace_id', 'action_items', type_='foreignkey')
    op.drop_column('action_items', 'workspace_id')
