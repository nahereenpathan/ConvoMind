"""add_description_to_workspaces

Revision ID: b1a2c3d4e5f6
Revises: d469ae317145
Create Date: 2026-09-17 10:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b1a2c3d4e5f6'
down_revision: Union[str, None] = 'd469ae317145'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('workspaces', sa.Column('description', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('workspaces', 'description')
