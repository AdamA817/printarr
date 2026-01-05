"""Add missing database indexes for common query patterns.

Revision ID: r6s7t8u9v0w1
Revises: q5r6s7t8u9v0
Create Date: 2026-01-05 19:30:00.000000

Issue: #220 - Performance optimization through better indexing
"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "r6s7t8u9v0w1"
down_revision: str | None = "q5r6s7t8u9v0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add missing indexes for common query patterns.

    These indexes optimize:
    1. Job listing (sorted by created_at)
    2. Design listing (sorted by updated_at)
    3. Queue queries (status + created_at for sorting)
    4. Design filtering (status + updated_at for sorting)
    5. Import record queries (detected_at sorting)
    """
    # Jobs: Add created_at index for sorting
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_jobs_created_at
        ON jobs (created_at DESC)
    """)

    # Jobs: Composite index for queue listing (status + created_at for sorting)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_jobs_status_created
        ON jobs (status, created_at DESC)
    """)

    # Designs: Add updated_at index for sorting
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_designs_updated_at
        ON designs (updated_at DESC)
    """)

    # Designs: Composite index for common filtering (status + created_at)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_designs_status_created
        ON designs (status, created_at DESC)
    """)

    # Designs: Composite index for status + updated_at sorting
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_designs_status_updated
        ON designs (status, updated_at DESC)
    """)

    # Import records: Add detected_at index for sorting
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_import_records_detected_at
        ON import_records (detected_at DESC)
    """)

    # Import records: Add status + detected_at composite for filtering
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_import_records_status_detected
        ON import_records (status, detected_at DESC)
    """)

    # Channels: Add created_at index for listing
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_channels_created_at
        ON channels (created_at DESC)
    """)


def downgrade() -> None:
    """Remove the indexes added in upgrade."""
    op.execute("DROP INDEX IF EXISTS ix_jobs_created_at")
    op.execute("DROP INDEX IF EXISTS ix_jobs_status_created")
    op.execute("DROP INDEX IF EXISTS ix_designs_updated_at")
    op.execute("DROP INDEX IF EXISTS ix_designs_status_created")
    op.execute("DROP INDEX IF EXISTS ix_designs_status_updated")
    op.execute("DROP INDEX IF EXISTS ix_import_records_detected_at")
    op.execute("DROP INDEX IF EXISTS ix_import_records_status_detected")
    op.execute("DROP INDEX IF EXISTS ix_channels_created_at")
