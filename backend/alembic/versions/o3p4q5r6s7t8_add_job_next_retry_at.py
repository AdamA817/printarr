"""Add next_retry_at column to jobs table (DEC-042).

Revision ID: o3p4q5r6s7t8
Revises: n2o3p4q5r6s7
Create Date: 2026-01-05 14:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "o3p4q5r6s7t8"
down_revision: Union[str, None] = "n2o3p4q5r6s7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add next_retry_at column for scheduled retries."""
    # Add the next_retry_at column
    op.add_column(
        "jobs",
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Create index for efficient retry scheduling queries
    op.create_index(
        "ix_jobs_next_retry_at",
        "jobs",
        ["next_retry_at"],
    )

    # Update max_attempts default from 3 to 4 for existing jobs
    # (4 attempts = 1 initial + 3 retries)
    op.execute(
        "UPDATE jobs SET max_attempts = 4 WHERE max_attempts = 3 AND status IN ('QUEUED', 'RUNNING')"
    )


def downgrade() -> None:
    """Remove next_retry_at column."""
    op.drop_index("ix_jobs_next_retry_at", "jobs")
    op.drop_column("jobs", "next_retry_at")
