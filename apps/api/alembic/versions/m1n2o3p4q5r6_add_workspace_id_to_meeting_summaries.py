"""add_workspace_id_to_meeting_summaries

Revision ID: m1n2o3p4q5r6
Revises: a91f0539d627
Create Date: 2026-09-22 19:35:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'm1n2o3p4q5r6'
down_revision: Union[str, None] = 'a91f0539d627'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add nullable workspace_id column
    op.add_column(
        'meeting_summaries',
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), nullable=True)
    )

    # 2. Backfill workspace_id from meetings table
    op.execute("""
        UPDATE meeting_summaries
        SET workspace_id = meetings.workspace_id
        FROM meetings
        WHERE meetings.id = meeting_summaries.meeting_id
    """)

    # 3. If any orphans remain (should not happen), set nullable=False and create FK & Index
    op.create_index(
        op.f('ix_meeting_summaries_workspace_id'),
        'meeting_summaries',
        ['workspace_id'],
        unique=False
    )
    op.create_foreign_key(
        'fk_meeting_summaries_workspace_id_workspaces',
        'meeting_summaries',
        'workspaces',
        ['workspace_id'],
        ['id'],
        ondelete='CASCADE'
    )


def downgrade() -> None:
    op.drop_constraint('fk_meeting_summaries_workspace_id_workspaces', 'meeting_summaries', type_='foreignkey')
    op.drop_index(op.f('ix_meeting_summaries_workspace_id'), table_name='meeting_summaries')
    op.drop_column('meeting_summaries', 'workspace_id')
