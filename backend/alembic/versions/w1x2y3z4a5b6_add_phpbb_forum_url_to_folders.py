"""Add phpbb_forum_url to import_source_folders.

Revision ID: w1x2y3z4a5b6
Revises: v0w1x2y3z4a5
Create Date: 2026-01-06 00:00:00.000000

Issue #242: Support multi-forum phpBB import sources.

Adds phpbb_forum_url field to import_source_folders table to allow
multiple forum pages under a single phpBB import source.
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "w1x2y3z4a5b6"
down_revision: str | None = "v0w1x2y3z4a5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add phpbb_forum_url column to import_source_folders."""
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "sqlite":
        with op.batch_alter_table("import_source_folders", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column("phpbb_forum_url", sa.String(1024), nullable=True)
            )
    else:
        op.add_column(
            "import_source_folders",
            sa.Column("phpbb_forum_url", sa.String(1024), nullable=True),
        )


def downgrade() -> None:
    """Remove phpbb_forum_url column from import_source_folders."""
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "sqlite":
        with op.batch_alter_table("import_source_folders", schema=None) as batch_op:
            batch_op.drop_column("phpbb_forum_url")
    else:
        op.drop_column("import_source_folders", "phpbb_forum_url")
