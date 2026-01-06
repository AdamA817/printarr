"""Add phpBB forum integration.

Revision ID: v0w1x2y3z4a5
Revises: u9v0w1x2y3z4
Create Date: 2026-01-06 00:00:00.000000

Issue #239: Add support for phpBB forum import sources.

This migration:
1. Creates the phpbb_credentials table for storing encrypted forum credentials
2. Adds PHPBB_FORUM to the ImportSourceType enum
3. Adds phpbb_credentials_id and phpbb_forum_url to import_sources
4. Adds payload_json to import_records for source-specific data
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "v0w1x2y3z4a5"
down_revision: str | None = "u9v0w1x2y3z4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add phpBB forum integration support."""
    bind = op.get_bind()
    dialect = bind.dialect.name

    # 1. Create phpbb_credentials table
    op.create_table(
        "phpbb_credentials",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("base_url", sa.String(512), nullable=False),
        sa.Column("username_encrypted", sa.Text(), nullable=False),
        sa.Column("password_encrypted", sa.Text(), nullable=False),
        sa.Column("session_cookies_encrypted", sa.Text(), nullable=True),
        sa.Column("session_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # 2. Add PHPBB_FORUM to ImportSourceType enum
    if dialect == "postgresql":
        # PostgreSQL requires explicit enum type alteration
        op.execute("ALTER TYPE importsourcetype ADD VALUE IF NOT EXISTS 'PHPBB_FORUM'")
    # SQLite doesn't have enum types, values are stored as strings

    # 3. Add phpbb columns to import_sources
    if dialect == "sqlite":
        with op.batch_alter_table("import_sources", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column("phpbb_credentials_id", sa.String(36), nullable=True)
            )
            batch_op.add_column(
                sa.Column("phpbb_forum_url", sa.String(1024), nullable=True)
            )
            batch_op.create_foreign_key(
                "fk_import_sources_phpbb_credentials_id",
                "phpbb_credentials",
                ["phpbb_credentials_id"],
                ["id"],
            )
    else:
        op.add_column(
            "import_sources",
            sa.Column("phpbb_credentials_id", sa.String(36), nullable=True),
        )
        op.add_column(
            "import_sources",
            sa.Column("phpbb_forum_url", sa.String(1024), nullable=True),
        )
        op.create_foreign_key(
            "fk_import_sources_phpbb_credentials_id",
            "import_sources",
            "phpbb_credentials",
            ["phpbb_credentials_id"],
            ["id"],
        )

    # 4. Add payload_json to import_records
    if dialect == "sqlite":
        with op.batch_alter_table("import_records", schema=None) as batch_op:
            batch_op.add_column(sa.Column("payload_json", sa.Text(), nullable=True))
    else:
        op.add_column(
            "import_records", sa.Column("payload_json", sa.Text(), nullable=True)
        )


def downgrade() -> None:
    """Remove phpBB forum integration support."""
    bind = op.get_bind()
    dialect = bind.dialect.name

    # 4. Drop payload_json from import_records
    if dialect == "sqlite":
        with op.batch_alter_table("import_records", schema=None) as batch_op:
            batch_op.drop_column("payload_json")
    else:
        op.drop_column("import_records", "payload_json")

    # 3. Drop phpbb columns from import_sources
    if dialect == "sqlite":
        with op.batch_alter_table("import_sources", schema=None) as batch_op:
            batch_op.drop_constraint(
                "fk_import_sources_phpbb_credentials_id", type_="foreignkey"
            )
            batch_op.drop_column("phpbb_forum_url")
            batch_op.drop_column("phpbb_credentials_id")
    else:
        op.drop_constraint(
            "fk_import_sources_phpbb_credentials_id",
            "import_sources",
            type_="foreignkey",
        )
        op.drop_column("import_sources", "phpbb_forum_url")
        op.drop_column("import_sources", "phpbb_credentials_id")

    # 2. Cannot remove enum value in PostgreSQL without recreating type
    # This is a known limitation - just leave the value in place

    # 1. Drop phpbb_credentials table
    op.drop_table("phpbb_credentials")
