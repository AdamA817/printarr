"""Add virtual channel support for import sources.

Revision ID: s7t8u9v0w1x2
Revises: r6s7t8u9v0w1
Create Date: 2026-01-05 20:00:00.000000

Issue: #237 - Create virtual channel for each import source
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "s7t8u9v0w1x2"
down_revision: str | None = "r6s7t8u9v0w1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add virtual channel columns and indexes.

    Changes:
    1. Add is_virtual boolean column (default False for existing channels)
    2. Add import_source_id FK column
    3. Make telegram_peer_id nullable (for virtual channels)
    4. Add indexes for new columns
    """
    # Add is_virtual column
    op.add_column(
        "channels",
        sa.Column("is_virtual", sa.Boolean(), nullable=False, server_default="false"),
    )

    # Add import_source_id FK column
    op.add_column(
        "channels",
        sa.Column("import_source_id", sa.String(36), nullable=True),
    )

    # Add foreign key constraint
    op.create_foreign_key(
        "fk_channels_import_source",
        "channels",
        "import_sources",
        ["import_source_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # Make telegram_peer_id nullable (for virtual channels)
    op.alter_column(
        "channels",
        "telegram_peer_id",
        existing_type=sa.String(64),
        nullable=True,
    )

    # Add indexes
    op.create_index("ix_channels_import_source", "channels", ["import_source_id"])
    op.create_index("ix_channels_virtual", "channels", ["is_virtual"])


def downgrade() -> None:
    """Remove virtual channel support."""
    # Drop indexes
    op.drop_index("ix_channels_virtual")
    op.drop_index("ix_channels_import_source")

    # Make telegram_peer_id non-nullable again
    # Note: This will fail if there are virtual channels with NULL telegram_peer_id
    op.alter_column(
        "channels",
        "telegram_peer_id",
        existing_type=sa.String(64),
        nullable=False,
    )

    # Drop foreign key and column
    op.drop_constraint("fk_channels_import_source", "channels", type_="foreignkey")
    op.drop_column("channels", "import_source_id")
    op.drop_column("channels", "is_virtual")
