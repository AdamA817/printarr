"""Fix duplicate virtual channels and add unique constraint.

Revision ID: t8u9v0w1x2y3
Revises: s7t8u9v0w1x2
Create Date: 2026-01-05 21:00:00.000000

Issue: #237 - Prevent duplicate virtual channels for same import source
"""
from collections.abc import Sequence

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "t8u9v0w1x2y3"
down_revision: str | None = "s7t8u9v0w1x2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Remove duplicate virtual channels and add unique constraint.

    For each import_source_id with multiple channels, keep only the oldest one.
    Then add a unique constraint to prevent future duplicates.
    """
    # Delete duplicate virtual channels, keeping only the first (oldest) one
    op.execute("""
        DELETE FROM channels
        WHERE id IN (
            SELECT id FROM (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY import_source_id
                           ORDER BY created_at ASC
                       ) as rn
                FROM channels
                WHERE import_source_id IS NOT NULL
            ) ranked
            WHERE rn > 1
        )
    """)

    # Add unique constraint on import_source_id (allows NULL, but only one non-NULL per value)
    op.create_unique_constraint(
        "uq_channels_import_source",
        "channels",
        ["import_source_id"],
    )


def downgrade() -> None:
    """Remove the unique constraint."""
    op.drop_constraint("uq_channels_import_source", "channels", type_="unique")
