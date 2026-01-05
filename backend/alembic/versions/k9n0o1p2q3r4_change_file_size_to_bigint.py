"""change_file_size_to_bigint

Revision ID: k9n0o1p2q3r4
Revises: j8m9n0o1p2q3
Create Date: 2026-01-04 12:00:00.000000

Change import_records.file_size from Integer to BigInteger.

Files larger than 2GB (int32 max: 2,147,483,647) overflow Integer columns.
BigInteger (int64) supports files up to 9.2 exabytes.

See issue #184 for details.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'k9n0o1p2q3r4'
down_revision: Union[str, Sequence[str], None] = 'j8m9n0o1p2q3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Change file_size column to BigInteger."""
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == 'postgresql':
        # PostgreSQL: Use ALTER COLUMN TYPE
        op.execute(
            "ALTER TABLE import_records ALTER COLUMN file_size TYPE BIGINT"
        )
    elif dialect == 'sqlite':
        # SQLite: INTEGER is already 64-bit, no change needed
        # SQLite's INTEGER type can hold values up to 2^63-1
        pass


def downgrade() -> None:
    """Revert file_size column to Integer (will fail if data >2GB exists)."""
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == 'postgresql':
        op.execute(
            "ALTER TABLE import_records ALTER COLUMN file_size TYPE INTEGER"
        )
    # SQLite: No change needed
