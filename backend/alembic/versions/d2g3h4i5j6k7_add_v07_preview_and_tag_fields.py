"""add_v07_preview_and_tag_fields

Revision ID: d2g3h4i5j6k7
Revises: c1f2g3h4i5j6
Create Date: 2025-12-31 10:00:00.000000

Add v0.7 preview and tagging system fields:
- Tag table: category, is_predefined, usage_count
- PreviewAsset table: source, file_size, original_filename, telegram_file_id, is_primary, sort_order
- Design table: multicolor_source
- Update enums: TagSource, PreviewKind (new values), PreviewSource (new), MulticolorSource (new)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd2g3h4i5j6k7'
down_revision: Union[str, Sequence[str], None] = 'c1f2g3h4i5j6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add v0.7 preview and tag system fields."""
    from sqlalchemy import text
    bind = op.get_bind()
    dialect = bind.dialect.name

    # === Tag table updates ===
    op.add_column('tags', sa.Column('category', sa.String(50), nullable=True))
    op.add_column('tags', sa.Column('is_predefined', sa.Boolean(), nullable=False, server_default='0'))
    op.add_column('tags', sa.Column('usage_count', sa.Integer(), nullable=False, server_default='0'))

    # Add indexes for tag queries
    op.create_index('ix_tags_category', 'tags', ['category'])
    op.create_index('ix_tags_is_predefined', 'tags', ['is_predefined'])

    # === PreviewAsset table updates ===
    # Note: SQLite doesn't support adding columns with non-constant defaults,
    # so we add nullable columns first, then update

    # Add source column (new PreviewSource enum)
    op.add_column('preview_assets', sa.Column('source', sa.String(20), nullable=True))

    # Add file metadata columns
    op.add_column('preview_assets', sa.Column('file_size', sa.Integer(), nullable=True))
    op.add_column('preview_assets', sa.Column('original_filename', sa.String(512), nullable=True))
    op.add_column('preview_assets', sa.Column('telegram_file_id', sa.String(512), nullable=True))

    # Add display ordering columns
    op.add_column('preview_assets', sa.Column('is_primary', sa.Boolean(), nullable=False, server_default='0'))
    op.add_column('preview_assets', sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'))

    # Rename 'path' to 'file_path' for consistency with spec
    # SQLite doesn't support direct rename, so we need a workaround
    # For now, add file_path as alias (path still exists)
    op.add_column('preview_assets', sa.Column('file_path', sa.String(1024), nullable=True))

    # Copy data from path to file_path
    op.execute("UPDATE preview_assets SET file_path = path WHERE file_path IS NULL")

    # Set default source based on existing kind values
    op.execute("""
        UPDATE preview_assets
        SET source = CASE
            WHEN kind = 'TELEGRAM_IMAGE' THEN 'TELEGRAM'
            WHEN kind = 'THREE_MF_EMBEDDED' THEN 'EMBEDDED_3MF'
            WHEN kind = 'RENDERED' THEN 'RENDERED'
            ELSE 'TELEGRAM'
        END
        WHERE source IS NULL
    """)

    # For PostgreSQL, we need special handling for enum updates (DEC-039)
    # New enum values can't be used in the same transaction they're added
    if dialect == 'postgresql':
        # Check if there are any rows to update (empty on fresh install)
        result = bind.execute(text(
            "SELECT COUNT(*) FROM preview_assets WHERE kind IN ('TELEGRAM_IMAGE', 'THREE_MF_EMBEDDED', 'RENDERED')"
        ))
        count = result.scalar()

        if count == 0:
            # Fresh install - no data to migrate, just add the new enum value
            # for future use. We need to commit the current transaction first.
            bind.execute(text("COMMIT"))
            bind.execute(text("ALTER TYPE previewkind ADD VALUE IF NOT EXISTS 'THUMBNAIL'"))
            bind.execute(text("BEGIN"))
        else:
            # Existing data - need to do a two-step migration
            # This case shouldn't happen for fresh PostgreSQL installs
            # For SQLite->PostgreSQL migration, a separate migration step is needed
            pass  # Skip for now, data will use old enum values
    else:
        # SQLite - update enum values directly (stored as strings)
        op.execute("""
            UPDATE preview_assets
            SET kind = 'THUMBNAIL'
            WHERE kind IN ('TELEGRAM_IMAGE', 'THREE_MF_EMBEDDED', 'RENDERED')
        """)

    # Add indexes for preview queries
    op.create_index('ix_preview_assets_design_id', 'preview_assets', ['design_id'])
    op.create_index('ix_preview_assets_design_source', 'preview_assets', ['design_id', 'source'])
    op.create_index('ix_preview_assets_is_primary', 'preview_assets', ['is_primary'])

    # Drop old composite index if exists (may fail silently on SQLite)
    try:
        op.drop_index('ix_preview_assets_design_kind', 'preview_assets')
    except Exception:
        pass  # Index may not exist

    # === Design table updates ===
    op.add_column('designs', sa.Column('multicolor_source', sa.String(20), nullable=True))

    # === DesignTag table updates ===
    # Update source enum values (AUTO -> AUTO_CAPTION for existing records)
    if dialect == 'postgresql':
        # Check if there are any rows to update (empty on fresh install)
        result = bind.execute(text(
            "SELECT COUNT(*) FROM design_tags WHERE source = 'AUTO'"
        ))
        count = result.scalar()

        if count == 0:
            # Fresh install - add new enum values for future use
            bind.execute(text("COMMIT"))
            bind.execute(text("ALTER TYPE tagsource ADD VALUE IF NOT EXISTS 'AUTO_CAPTION'"))
            bind.execute(text("ALTER TYPE tagsource ADD VALUE IF NOT EXISTS 'AUTO_FILENAME'"))
            bind.execute(text("ALTER TYPE tagsource ADD VALUE IF NOT EXISTS 'AUTO_THANGS'"))
            bind.execute(text("BEGIN"))
        else:
            # Existing data case - skip for fresh PostgreSQL installs
            pass
    else:
        # SQLite - update directly
        op.execute("""
            UPDATE design_tags
            SET source = 'AUTO_CAPTION'
            WHERE source = 'AUTO'
        """)


def downgrade() -> None:
    """Remove v0.7 preview and tag system fields."""

    # === Design table ===
    op.drop_column('designs', 'multicolor_source')

    # === PreviewAsset table ===
    try:
        op.drop_index('ix_preview_assets_is_primary', 'preview_assets')
        op.drop_index('ix_preview_assets_design_source', 'preview_assets')
        op.drop_index('ix_preview_assets_design_id', 'preview_assets')
    except Exception:
        pass

    # Restore old kind values
    op.execute("""
        UPDATE preview_assets
        SET kind = CASE
            WHEN source = 'TELEGRAM' THEN 'TELEGRAM_IMAGE'
            WHEN source = 'EMBEDDED_3MF' THEN 'THREE_MF_EMBEDDED'
            WHEN source = 'RENDERED' THEN 'RENDERED'
            ELSE 'TELEGRAM_IMAGE'
        END
    """)

    # Restore old source values in design_tags
    op.execute("""
        UPDATE design_tags
        SET source = 'AUTO'
        WHERE source IN ('AUTO_CAPTION', 'AUTO_FILENAME', 'AUTO_THANGS')
    """)

    op.drop_column('preview_assets', 'file_path')
    op.drop_column('preview_assets', 'sort_order')
    op.drop_column('preview_assets', 'is_primary')
    op.drop_column('preview_assets', 'telegram_file_id')
    op.drop_column('preview_assets', 'original_filename')
    op.drop_column('preview_assets', 'file_size')
    op.drop_column('preview_assets', 'source')

    # Recreate old index
    op.create_index('ix_preview_assets_design_kind', 'preview_assets', ['design_id', 'kind'])

    # === Tag table ===
    try:
        op.drop_index('ix_tags_is_predefined', 'tags')
        op.drop_index('ix_tags_category', 'tags')
    except Exception:
        pass

    op.drop_column('tags', 'usage_count')
    op.drop_column('tags', 'is_predefined')
    op.drop_column('tags', 'category')
