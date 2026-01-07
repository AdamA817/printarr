"""Add AI_ANALYZE_DESIGN to jobtype enum.

Revision ID: x2y3z4a5b6c7
Revises: w1x2y3z4a5b6
Create Date: 2026-01-07 00:00:00.000000

Issue #248: Add AI analysis job type for Google Gemini integration.

Adds AI_ANALYZE_DESIGN value to the jobtype PostgreSQL enum to support
the new AI-powered design tagging feature (DEC-043).
"""
from collections.abc import Sequence

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "x2y3z4a5b6c7"
down_revision: str | None = "w1x2y3z4a5b6"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    """Add AI_ANALYZE_DESIGN to jobtype enum."""
    # PostgreSQL requires ALTER TYPE to add enum values
    op.execute("ALTER TYPE jobtype ADD VALUE IF NOT EXISTS 'AI_ANALYZE_DESIGN'")


def downgrade() -> None:
    """Remove AI_ANALYZE_DESIGN from jobtype enum.

    Note: PostgreSQL doesn't support removing enum values directly.
    This would require recreating the enum type, which is complex
    and risky for production data. Leaving as no-op.
    """
    pass
