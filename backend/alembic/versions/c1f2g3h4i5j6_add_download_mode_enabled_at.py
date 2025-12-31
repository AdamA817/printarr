"""add_download_mode_enabled_at

Revision ID: c1f2g3h4i5j6
Revises: b9e6f3a2c5d7
Create Date: 2025-12-30 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1f2g3h4i5j6'
down_revision: Union[str, Sequence[str], None] = 'b9e6f3a2c5d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add download_mode_enabled_at column to channels table."""
    op.add_column(
        'channels',
        sa.Column('download_mode_enabled_at', sa.DateTime(), nullable=True)
    )


def downgrade() -> None:
    """Remove download_mode_enabled_at column from channels table."""
    op.drop_column('channels', 'download_mode_enabled_at')
