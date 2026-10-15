"""merge_billing_and_notification_heads

Revision ID: a91f0539d627
Revises: e73819fa991d, k0l1m2n3o4p5
Create Date: 2026-09-20 09:41:47.856028

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a91f0539d627'
down_revision: Union[str, None] = ('e73819fa991d', 'k0l1m2n3o4p5')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
