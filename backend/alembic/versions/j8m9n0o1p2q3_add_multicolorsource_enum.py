"""add_multicolorsource_enum

Revision ID: j8m9n0o1p2q3
Revises: i7l8m9n0o1p2
Create Date: 2026-01-04 11:00:00.000000

Add missing MulticolorSource enum type for PostgreSQL.

This migration creates the 'multicolorsource' enum type that was missing
from the initial schema. The enum is used in designs.multicolor_source
column (added in DEC-029).

See issue #180 for details.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'j8m9n0o1p2q3'
down_revision: Union[str, Sequence[str], None] = 'i7l8m9n0o1p2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create multicolorsource enum type for PostgreSQL."""
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == 'postgresql':
        # Check if the type already exists (may have been manually created as workaround)
        result = bind.execute(
            "SELECT 1 FROM pg_type WHERE typname = 'multicolorsource'"
        ).fetchone()

        if not result:
            op.execute(
                "CREATE TYPE multicolorsource AS ENUM ('HEURISTIC', '3MF_ANALYSIS', 'USER_OVERRIDE')"
            )
    # SQLite: No enum types needed - stores as text


def downgrade() -> None:
    """Drop multicolorsource enum type for PostgreSQL."""
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == 'postgresql':
        # Note: Can only drop if not in use by any columns
        # The column would need to be altered first
        op.execute("DROP TYPE IF EXISTS multicolorsource")
    # SQLite: No action needed
