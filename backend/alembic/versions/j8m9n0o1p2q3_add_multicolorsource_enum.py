"""add_missing_postgresql_enums

Revision ID: j8m9n0o1p2q3
Revises: i7l8m9n0o1p2
Create Date: 2026-01-04 11:00:00.000000

Add missing enum types for PostgreSQL.

This migration creates enum types that were missing from the initial schema
because development used SQLite (which doesn't require explicit enum types).

Enums added:
- multicolorsource: Used in designs.multicolor_source (DEC-029)
- previewsource: Used in preview_assets.source (DEC-027)

See issue #180 for details.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'j8m9n0o1p2q3'
down_revision: Union[str, Sequence[str], None] = 'i7l8m9n0o1p2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Enum definitions that need to be created for PostgreSQL
MISSING_ENUMS = {
    'multicolorsource': ['HEURISTIC', '3MF_ANALYSIS', 'USER_OVERRIDE'],
    'previewsource': ['TELEGRAM', 'THANGS', 'EMBEDDED_3MF', 'RENDERED', 'ARCHIVE'],
}


def upgrade() -> None:
    """Create missing enum types for PostgreSQL."""
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == 'postgresql':
        for enum_name, values in MISSING_ENUMS.items():
            # Check if the type already exists (may have been manually created as workaround)
            result = bind.execute(
                sa.text(f"SELECT 1 FROM pg_type WHERE typname = '{enum_name}'")
            ).fetchone()

            if not result:
                values_str = ", ".join(f"'{v}'" for v in values)
                op.execute(f"CREATE TYPE {enum_name} AS ENUM ({values_str})")
    # SQLite: No enum types needed - stores as text


def downgrade() -> None:
    """Drop missing enum types for PostgreSQL."""
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == 'postgresql':
        for enum_name in MISSING_ENUMS:
            # Note: Can only drop if not in use by any columns
            op.execute(f"DROP TYPE IF EXISTS {enum_name}")
    # SQLite: No action needed
