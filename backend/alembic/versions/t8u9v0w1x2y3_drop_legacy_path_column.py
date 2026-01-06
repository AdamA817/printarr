"""Drop legacy path column from preview_assets.

Revision ID: t8u9v0w1x2y3
Revises: s7t8u9v0w1x2
Create Date: 2026-01-06 00:00:00.000000

The initial schema created preview_assets with a `path` column.
Migration d2g3h4i5j6k7 added `file_path` as the new column name but
didn't drop `path`. The model now uses `file_path`, causing NOT NULL
violations when inserting new rows (path stays NULL).

This migration drops the legacy `path` column.
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "t8u9v0w1x2y3"
down_revision: str | None = "s7t8u9v0w1x2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Drop the legacy path column."""
    # Get dialect for conditional handling
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "sqlite":
        # SQLite requires batch mode for column drops
        with op.batch_alter_table("preview_assets", schema=None) as batch_op:
            batch_op.drop_column("path")
    else:
        # PostgreSQL can drop columns directly
        op.drop_column("preview_assets", "path")


def downgrade() -> None:
    """Re-add the path column and populate from file_path."""
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "sqlite":
        with op.batch_alter_table("preview_assets", schema=None) as batch_op:
            batch_op.add_column(sa.Column("path", sa.String(1024), nullable=True))
        # Copy data from file_path to path
        op.execute("UPDATE preview_assets SET path = file_path")
        # Make NOT NULL (SQLite doesn't support ALTER COLUMN, but batch mode handles it)
        with op.batch_alter_table("preview_assets", schema=None) as batch_op:
            batch_op.alter_column("path", nullable=False)
    else:
        op.add_column("preview_assets", sa.Column("path", sa.String(1024), nullable=True))
        op.execute("UPDATE preview_assets SET path = file_path")
        op.alter_column("preview_assets", "path", nullable=False)
