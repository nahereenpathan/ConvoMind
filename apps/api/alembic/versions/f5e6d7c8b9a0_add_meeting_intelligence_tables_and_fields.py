"""add_meeting_intelligence_tables_and_fields

Revision ID: f5e6d7c8b9a0
Revises: e4d5c6b7a8b9
Create Date: 2026-09-17 12:16:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f5e6d7c8b9a0'
down_revision: Union[str, None] = 'e4d5c6b7a8b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create meeting_intelligence_jobs table
    op.create_table(
        'meeting_intelligence_jobs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('meeting_id', sa.UUID(), nullable=False),
        sa.Column('workspace_id', sa.UUID(), nullable=False),
        sa.Column(
            'status',
            sa.Enum('QUEUED', 'PROCESSING', 'COMPLETED', 'FAILED', name='intelligence_status', native_enum=False),
            nullable=False,
            server_default='QUEUED',
        ),
        sa.Column('provider', sa.String(length=100), nullable=False, server_default='mock'),
        sa.Column('model', sa.String(length=100), nullable=False, server_default='mock-model'),
        sa.Column('prompt_version', sa.String(length=50), nullable=False, server_default='v1'),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('processing_duration', sa.Float(), nullable=True),
        sa.Column('token_usage', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['meeting_id'], ['meetings.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_meeting_intelligence_jobs_meeting_id'), 'meeting_intelligence_jobs', ['meeting_id'], unique=False)
    op.create_index(op.f('ix_meeting_intelligence_jobs_workspace_id'), 'meeting_intelligence_jobs', ['workspace_id'], unique=False)
    op.create_index(op.f('ix_meeting_intelligence_jobs_status'), 'meeting_intelligence_jobs', ['status'], unique=False)

    # 2. Add columns to meeting_summaries
    op.add_column('meeting_summaries', sa.Column('detailed_summary', sa.Text(), nullable=True))
    op.add_column('meeting_summaries', sa.Column('risks_and_concerns', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('meeting_summaries', sa.Column('requirements_and_notes', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('meeting_summaries', sa.Column('follow_up_suggestions', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('meeting_summaries', sa.Column('provider', sa.String(length=100), nullable=True))
    op.add_column('meeting_summaries', sa.Column('prompt_version', sa.String(length=50), nullable=False, server_default='v1'))
    op.add_column('meeting_summaries', sa.Column('processing_duration', sa.Float(), nullable=True))
    op.add_column('meeting_summaries', sa.Column('token_usage', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('meeting_summaries', sa.Column('version', sa.Integer(), nullable=False, server_default='1'))
    op.add_column('meeting_summaries', sa.Column('job_id', sa.UUID(), nullable=True))
    op.create_foreign_key(
        'fk_meeting_summaries_job_id',
        'meeting_summaries',
        'meeting_intelligence_jobs',
        ['job_id'],
        ['id'],
        ondelete='SET NULL',
    )
    op.create_index(op.f('ix_meeting_summaries_version'), 'meeting_summaries', ['version'], unique=False)
    op.create_index(op.f('ix_meeting_summaries_job_id'), 'meeting_summaries', ['job_id'], unique=False)

    # 3. Add columns to action_items
    op.add_column('action_items', sa.Column('assignee_name', sa.String(length=255), nullable=True))
    op.add_column('action_items', sa.Column('timestamp_marker', sa.Float(), nullable=True))
    op.add_column('action_items', sa.Column('source_segment_id', sa.UUID(), nullable=True))
    op.add_column('action_items', sa.Column('version', sa.Integer(), nullable=False, server_default='1'))
    op.add_column('action_items', sa.Column('job_id', sa.UUID(), nullable=True))
    op.create_foreign_key(
        'fk_action_items_source_segment_id',
        'action_items',
        'transcript_segments',
        ['source_segment_id'],
        ['id'],
        ondelete='SET NULL',
    )
    op.create_foreign_key(
        'fk_action_items_job_id',
        'action_items',
        'meeting_intelligence_jobs',
        ['job_id'],
        ['id'],
        ondelete='SET NULL',
    )
    op.create_index(op.f('ix_action_items_source_segment_id'), 'action_items', ['source_segment_id'], unique=False)
    op.create_index(op.f('ix_action_items_version'), 'action_items', ['version'], unique=False)
    op.create_index(op.f('ix_action_items_job_id'), 'action_items', ['job_id'], unique=False)

    # 4. Add columns to decisions
    op.add_column('decisions', sa.Column('source_segment_id', sa.UUID(), nullable=True))
    op.add_column('decisions', sa.Column('version', sa.Integer(), nullable=False, server_default='1'))
    op.add_column('decisions', sa.Column('job_id', sa.UUID(), nullable=True))
    op.create_foreign_key(
        'fk_decisions_source_segment_id',
        'decisions',
        'transcript_segments',
        ['source_segment_id'],
        ['id'],
        ondelete='SET NULL',
    )
    op.create_foreign_key(
        'fk_decisions_job_id',
        'decisions',
        'meeting_intelligence_jobs',
        ['job_id'],
        ['id'],
        ondelete='SET NULL',
    )
    op.create_index(op.f('ix_decisions_source_segment_id'), 'decisions', ['source_segment_id'], unique=False)
    op.create_index(op.f('ix_decisions_version'), 'decisions', ['version'], unique=False)
    op.create_index(op.f('ix_decisions_job_id'), 'decisions', ['job_id'], unique=False)

    # 5. Add columns to meeting_questions
    op.add_column('meeting_questions', sa.Column('asked_by_speaker_name', sa.String(length=255), nullable=True))
    op.add_column('meeting_questions', sa.Column('source_segment_id', sa.UUID(), nullable=True))
    op.add_column('meeting_questions', sa.Column('version', sa.Integer(), nullable=False, server_default='1'))
    op.add_column('meeting_questions', sa.Column('job_id', sa.UUID(), nullable=True))
    op.create_foreign_key(
        'fk_meeting_questions_source_segment_id',
        'meeting_questions',
        'transcript_segments',
        ['source_segment_id'],
        ['id'],
        ondelete='SET NULL',
    )
    op.create_foreign_key(
        'fk_meeting_questions_job_id',
        'meeting_questions',
        'meeting_intelligence_jobs',
        ['job_id'],
        ['id'],
        ondelete='SET NULL',
    )
    op.create_index(op.f('ix_meeting_questions_source_segment_id'), 'meeting_questions', ['source_segment_id'], unique=False)
    op.create_index(op.f('ix_meeting_questions_version'), 'meeting_questions', ['version'], unique=False)
    op.create_index(op.f('ix_meeting_questions_job_id'), 'meeting_questions', ['job_id'], unique=False)


def downgrade() -> None:
    # 5. Remove columns from meeting_questions
    op.drop_index(op.f('ix_meeting_questions_job_id'), table_name='meeting_questions')
    op.drop_index(op.f('ix_meeting_questions_version'), table_name='meeting_questions')
    op.drop_index(op.f('ix_meeting_questions_source_segment_id'), table_name='meeting_questions')
    op.drop_constraint('fk_meeting_questions_job_id', 'meeting_questions', type_='foreignkey')
    op.drop_constraint('fk_meeting_questions_source_segment_id', 'meeting_questions', type_='foreignkey')
    op.drop_column('meeting_questions', 'job_id')
    op.drop_column('meeting_questions', 'version')
    op.drop_column('meeting_questions', 'source_segment_id')
    op.drop_column('meeting_questions', 'asked_by_speaker_name')

    # 4. Remove columns from decisions
    op.drop_index(op.f('ix_decisions_job_id'), table_name='decisions')
    op.drop_index(op.f('ix_decisions_version'), table_name='decisions')
    op.drop_index(op.f('ix_decisions_source_segment_id'), table_name='decisions')
    op.drop_constraint('fk_decisions_job_id', 'decisions', type_='foreignkey')
    op.drop_constraint('fk_decisions_source_segment_id', 'decisions', type_='foreignkey')
    op.drop_column('decisions', 'job_id')
    op.drop_column('decisions', 'version')
    op.drop_column('decisions', 'source_segment_id')

    # 3. Remove columns from action_items
    op.drop_index(op.f('ix_action_items_job_id'), table_name='action_items')
    op.drop_index(op.f('ix_action_items_version'), table_name='action_items')
    op.drop_index(op.f('ix_action_items_source_segment_id'), table_name='action_items')
    op.drop_constraint('fk_action_items_job_id', 'action_items', type_='foreignkey')
    op.drop_constraint('fk_action_items_source_segment_id', 'action_items', type_='foreignkey')
    op.drop_column('action_items', 'job_id')
    op.drop_column('action_items', 'version')
    op.drop_column('action_items', 'source_segment_id')
    op.drop_column('action_items', 'timestamp_marker')
    op.drop_column('action_items', 'assignee_name')

    # 2. Remove columns from meeting_summaries
    op.drop_index(op.f('ix_meeting_summaries_job_id'), table_name='meeting_summaries')
    op.drop_index(op.f('ix_meeting_summaries_version'), table_name='meeting_summaries')
    op.drop_constraint('fk_meeting_summaries_job_id', 'meeting_summaries', type_='foreignkey')
    op.drop_column('meeting_summaries', 'job_id')
    op.drop_column('meeting_summaries', 'version')
    op.drop_column('meeting_summaries', 'token_usage')
    op.drop_column('meeting_summaries', 'processing_duration')
    op.drop_column('meeting_summaries', 'prompt_version')
    op.drop_column('meeting_summaries', 'provider')
    op.drop_column('meeting_summaries', 'follow_up_suggestions')
    op.drop_column('meeting_summaries', 'requirements_and_notes')
    op.drop_column('meeting_summaries', 'risks_and_concerns')
    op.drop_column('meeting_summaries', 'detailed_summary')

    # 1. Drop meeting_intelligence_jobs table
    op.drop_index(op.f('ix_meeting_intelligence_jobs_status'), table_name='meeting_intelligence_jobs')
    op.drop_index(op.f('ix_meeting_intelligence_jobs_workspace_id'), table_name='meeting_intelligence_jobs')
    op.drop_index(op.f('ix_meeting_intelligence_jobs_meeting_id'), table_name='meeting_intelligence_jobs')
    op.drop_table('meeting_intelligence_jobs')
