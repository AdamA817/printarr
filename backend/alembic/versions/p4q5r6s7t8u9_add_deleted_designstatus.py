"""Add DELETED to designstatus enum.

Revision ID: p4q5r6s7t8u9
Revises: o3p4q5r6s7t8
Create Date: 2026-01-05 17:30:00.000000

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "p4q5r6s7t8u9"
down_revision: str | None = "o3p4q5r6s7t8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add DELETED value to designstatus enum for duplicate merge operations."""
    # PostgreSQL requires ALTER TYPE to add new enum values
    op.execute("ALTER TYPE designstatus ADD VALUE IF NOT EXISTS 'DELETED'")


def downgrade() -> None:
    """Remove DELETED value from designstatus enum.

    Note: PostgreSQL doesn't support removing enum values directly.
    This would require recreating the enum, which is complex and risky.
    For safety, we leave the value in place on downgrade.
    """
    pass
