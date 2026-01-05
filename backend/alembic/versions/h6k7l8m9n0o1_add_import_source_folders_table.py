"""add_import_source_folders_table

Revision ID: h6k7l8m9n0o1
Revises: g5j6k7l8m9n0
Create Date: 2026-01-02 18:00:00.000000

Add ImportSourceFolder table for multi-folder import sources (DEC-038).

This migration:
1. Creates the import_source_folders table
2. Adds import_source_folder_id to import_records
3. Migrates existing single-folder sources to the new folder table
4. Updates import_records to reference the new folders
"""
from typing import Sequence, Union
from datetime import datetime, timezone
import uuid

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'h6k7l8m9n0o1'
down_revision: Union[str, Sequence[str], None] = 'g5j6k7l8m9n0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add import_source_folders table and migrate data."""
    # 1. Create import_source_folders table
    op.create_table(
        'import_source_folders',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('import_source_id', sa.String(36), nullable=False),
        sa.Column('name', sa.String(255), nullable=True),
        sa.Column('google_drive_url', sa.String(1024), nullable=True),
        sa.Column('google_folder_id', sa.String(128), nullable=True),
        sa.Column('folder_path', sa.String(1024), nullable=True),
        sa.Column('import_profile_id', sa.String(36), nullable=True),
        sa.Column('default_designer', sa.String(255), nullable=True),
        sa.Column('default_tags_json', sa.Text(), nullable=True),
        sa.Column('enabled', sa.Boolean(), default=True, nullable=False),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('sync_cursor', sa.String(512), nullable=True),
        sa.Column('last_sync_error', sa.Text(), nullable=True),
        sa.Column('items_detected', sa.Integer(), default=0, nullable=False),
        sa.Column('items_imported', sa.Integer(), default=0, nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(
            ['import_source_id'], ['import_sources.id'],
            ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(
            ['import_profile_id'], ['import_profiles.id'],
        ),
    )

    # Create indexes for import_source_folders
    op.create_index(
        'ix_import_source_folders_source',
        'import_source_folders',
        ['import_source_id']
    )
    op.create_index(
        'ix_import_source_folders_enabled',
        'import_source_folders',
        ['enabled']
    )
    op.create_index(
        'ix_import_source_folders_google_id',
        'import_source_folders',
        ['google_folder_id']
    )

    # 2. Add import_source_folder_id column to import_records
    op.add_column(
        'import_records',
        sa.Column('import_source_folder_id', sa.String(36), nullable=True)
    )

    # Add foreign key constraint
    op.create_foreign_key(
        'fk_import_records_folder',
        'import_records',
        'import_source_folders',
        ['import_source_folder_id'],
        ['id'],
        ondelete='CASCADE'
    )

    # Create new indexes for import_records
    op.create_index(
        'ix_import_records_folder',
        'import_records',
        ['import_source_folder_id']
    )

    # Note: We need to drop the old unique index before creating the new one
    # to avoid conflicts during the transition
    # The old index ix_import_records_source_path will remain for backward compatibility

    # 3. Migrate existing data
    # This uses raw SQL for SQLite compatibility
    connection = op.get_bind()

    # Get all import sources with folder data
    sources = connection.execute(
        sa.text("""
            SELECT id, google_drive_url, google_drive_folder_id, folder_path,
                   import_profile_id, default_designer, default_tags_json,
                   last_sync_at, last_sync_error, items_imported, created_at
            FROM import_sources
            WHERE google_drive_folder_id IS NOT NULL OR folder_path IS NOT NULL
        """)
    ).fetchall()

    # Create a folder for each source and update records
    for source in sources:
        folder_id = str(uuid.uuid4())

        # Insert folder
        connection.execute(
            sa.text("""
                INSERT INTO import_source_folders (
                    id, import_source_id, name, google_drive_url, google_folder_id,
                    folder_path, import_profile_id, default_designer, default_tags_json,
                    enabled, last_synced_at, sync_cursor, last_sync_error,
                    items_detected, items_imported, created_at
                ) VALUES (
                    :folder_id, :source_id, NULL, :gdrive_url, :gdrive_folder_id,
                    :folder_path, :profile_id, :designer, :tags,
                    1, :last_sync, NULL, :sync_error,
                    0, :items_imported, :created_at
                )
            """),
            {
                'folder_id': folder_id,
                'source_id': source[0],  # id
                'gdrive_url': source[1],  # google_drive_url
                'gdrive_folder_id': source[2],  # google_drive_folder_id
                'folder_path': source[3],  # folder_path
                'profile_id': source[4],  # import_profile_id
                'designer': source[5],  # default_designer
                'tags': source[6],  # default_tags_json
                'last_sync': source[7],  # last_sync_at
                'sync_error': source[8],  # last_sync_error
                'items_imported': source[9] or 0,  # items_imported
                'created_at': source[10] or datetime.now(timezone.utc),  # created_at
            }
        )

        # Update import_records to reference the new folder
        connection.execute(
            sa.text("""
                UPDATE import_records
                SET import_source_folder_id = :folder_id
                WHERE import_source_id = :source_id
            """),
            {'folder_id': folder_id, 'source_id': source[0]}
        )

    # 4. Make import_source_id nullable in import_records (it's now deprecated)
    # SQLite doesn't support ALTER COLUMN, so we skip this for SQLite
    # The column is already nullable in the model


def downgrade() -> None:
    """Remove import_source_folders table and revert changes."""
    # Drop the new index
    op.drop_index('ix_import_records_folder', table_name='import_records')

    # Drop foreign key
    op.drop_constraint('fk_import_records_folder', 'import_records', type_='foreignkey')

    # Drop the new column
    op.drop_column('import_records', 'import_source_folder_id')

    # Drop import_source_folders indexes
    op.drop_index('ix_import_source_folders_google_id', table_name='import_source_folders')
    op.drop_index('ix_import_source_folders_enabled', table_name='import_source_folders')
    op.drop_index('ix_import_source_folders_source', table_name='import_source_folders')

    # Drop import_source_folders table
    op.drop_table('import_source_folders')
