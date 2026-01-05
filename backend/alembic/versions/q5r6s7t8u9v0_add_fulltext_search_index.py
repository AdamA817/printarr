"""Add full-text search index for designs.

Revision ID: q5r6s7t8u9v0
Revises: p4q5r6s7t8u9
Create Date: 2026-01-05 19:00:00.000000

Issue: #218 - Full-text search for designs at scale (10,000+)
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "q5r6s7t8u9v0"
down_revision: str | None = "p4q5r6s7t8u9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add full-text search support for designs table.

    Creates:
    1. pg_trgm extension for trigram similarity searches
    2. search_vector tsvector column (generated from title + designer)
    3. GIN index on search_vector for fast full-text queries
    4. Trigram indexes on title and designer for ILIKE fallback
    """
    # Enable pg_trgm extension for trigram support
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # Add search_vector column as a generated column
    # This automatically updates when canonical_title or canonical_designer changes
    op.execute("""
        ALTER TABLE designs
        ADD COLUMN IF NOT EXISTS search_vector tsvector
        GENERATED ALWAYS AS (
            setweight(to_tsvector('english', coalesce(canonical_title, '')), 'A') ||
            setweight(to_tsvector('english', coalesce(canonical_designer, '')), 'B')
        ) STORED
    """)

    # Create GIN index for full-text search
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_designs_search_vector
        ON designs USING gin (search_vector)
    """)

    # Create trigram indexes for ILIKE queries (fallback/partial matching)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_designs_title_trgm
        ON designs USING gin (canonical_title gin_trgm_ops)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_designs_designer_trgm
        ON designs USING gin (canonical_designer gin_trgm_ops)
    """)


def downgrade() -> None:
    """Remove full-text search indexes and columns."""
    # Drop indexes
    op.execute("DROP INDEX IF EXISTS ix_designs_search_vector")
    op.execute("DROP INDEX IF EXISTS ix_designs_title_trgm")
    op.execute("DROP INDEX IF EXISTS ix_designs_designer_trgm")

    # Drop search_vector column
    op.execute("ALTER TABLE designs DROP COLUMN IF EXISTS search_vector")

    # Note: We don't drop the pg_trgm extension as other things may depend on it
