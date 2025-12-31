"""add_job_result_json

Revision ID: a8d5f2e1b3c4
Revises: 3eec33a95b63
Create Date: 2025-12-30 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a8d5f2e1b3c4'
down_revision: Union[str, Sequence[str], None] = '3eec33a95b63'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add result_json column to jobs table."""
    op.add_column('jobs', sa.Column('result_json', sa.Text(), nullable=True))


def downgrade() -> None:
    """Remove result_json column from jobs table."""
    op.drop_column('jobs', 'result_json')
