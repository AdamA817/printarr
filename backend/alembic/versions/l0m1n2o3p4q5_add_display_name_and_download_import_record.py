"""add_display_name_and_download_import_record

Revision ID: l0m1n2o3p4q5
Revises: k9n0o1p2q3r4
Create Date: 2026-01-05 10:00:00.000000

Add display_name column to jobs table and DOWNLOAD_IMPORT_RECORD enum value.
Part of DEC-040: Per-design download jobs for import sources.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'l0m1n2o3p4q5'
down_revision: Union[str, Sequence[str], None] = 'k9n0o1p2q3r4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add display_name column and DOWNLOAD_IMPORT_RECORD enum."""
    bind = op.get_bind()
    dialect = bind.dialect.name

    # Add display_name column to jobs table
    op.add_column('jobs', sa.Column('display_name', sa.String(512), nullable=True))

    # Add DOWNLOAD_IMPORT_RECORD to jobtype enum (PostgreSQL only)
    if dialect == 'postgresql':
        # Check if value already exists
        result = bind.execute(
            sa.text("""
                SELECT 1 FROM pg_enum
                WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = 'jobtype')
                AND enumlabel = 'DOWNLOAD_IMPORT_RECORD'
            """)
        ).fetchone()

        if not result:
            op.execute("ALTER TYPE jobtype ADD VALUE IF NOT EXISTS 'DOWNLOAD_IMPORT_RECORD'")


def downgrade() -> None:
    """Remove display_name column."""
    # Drop the column
    op.drop_column('jobs', 'display_name')

    # Note: Cannot remove enum values in PostgreSQL without recreating the type
    # The DOWNLOAD_IMPORT_RECORD value will remain but be unused
