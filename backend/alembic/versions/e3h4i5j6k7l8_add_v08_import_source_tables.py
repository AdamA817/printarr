"""add_v08_import_source_tables

Revision ID: e3h4i5j6k7l8
Revises: d2g3h4i5j6k7
Create Date: 2026-01-02 10:00:00.000000

Add v0.8 Manual Imports data models:
- ImportProfile table: Configurable folder structure parsing profiles
- GoogleCredentials table: OAuth token storage for Google Drive
- ImportSource table: Import sources (Google Drive, Upload, Bulk Folder)
- Design.import_source_id: FK to track import source for non-Telegram designs

See DEC-033, DEC-034, DEC-035 for design decisions.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e3h4i5j6k7l8'
down_revision: Union[str, Sequence[str], None] = 'd2g3h4i5j6k7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add v0.8 import source tables and relationships."""

    # === Create import_profiles table ===
    op.create_table(
        'import_profiles',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False, unique=True),
        sa.Column('description', sa.String(1024), nullable=True),
        sa.Column('is_builtin', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('config_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )

    # === Create google_credentials table ===
    op.create_table(
        'google_credentials',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('email', sa.String(255), nullable=False, unique=True),
        sa.Column('access_token_encrypted', sa.Text(), nullable=True),
        sa.Column('refresh_token_encrypted', sa.Text(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )

    # === Create import_sources table ===
    op.create_table(
        'import_sources',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('source_type', sa.String(20), nullable=False),  # ImportSourceType enum
        sa.Column('status', sa.String(20), nullable=False, server_default='PENDING'),  # ImportSourceStatus enum
        # Google Drive fields
        sa.Column('google_drive_url', sa.String(1024), nullable=True),
        sa.Column('google_drive_folder_id', sa.String(128), nullable=True),
        sa.Column('google_credentials_id', sa.String(36), sa.ForeignKey('google_credentials.id'), nullable=True),
        # Bulk folder fields
        sa.Column('folder_path', sa.String(1024), nullable=True),
        # Import profile
        sa.Column('import_profile_id', sa.String(36), sa.ForeignKey('import_profiles.id'), nullable=True),
        # Default metadata
        sa.Column('default_designer', sa.String(255), nullable=True),
        sa.Column('default_tags_json', sa.Text(), nullable=True),
        # Sync settings
        sa.Column('sync_enabled', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('sync_interval_hours', sa.Integer(), nullable=False, server_default='1'),
        # Sync state
        sa.Column('last_sync_at', sa.DateTime(), nullable=True),
        sa.Column('last_sync_error', sa.Text(), nullable=True),
        sa.Column('items_imported', sa.Integer(), nullable=False, server_default='0'),
        # Timestamps
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )

    # Create indexes for import_sources
    op.create_index('ix_import_sources_type', 'import_sources', ['source_type'])
    op.create_index('ix_import_sources_status', 'import_sources', ['status'])
    op.create_index('ix_import_sources_sync', 'import_sources', ['sync_enabled', 'last_sync_at'])

    # === Add import_source_id to designs table ===
    op.add_column('designs', sa.Column('import_source_id', sa.String(36), nullable=True))
    op.create_foreign_key(
        'fk_designs_import_source_id',
        'designs',
        'import_sources',
        ['import_source_id'],
        ['id']
    )
    op.create_index('ix_designs_import_source_id', 'designs', ['import_source_id'])


def downgrade() -> None:
    """Remove v0.8 import source tables and relationships."""

    # === Remove import_source_id from designs ===
    op.drop_index('ix_designs_import_source_id', 'designs')
    op.drop_constraint('fk_designs_import_source_id', 'designs', type_='foreignkey')
    op.drop_column('designs', 'import_source_id')

    # === Drop import_sources table ===
    op.drop_index('ix_import_sources_sync', 'import_sources')
    op.drop_index('ix_import_sources_status', 'import_sources')
    op.drop_index('ix_import_sources_type', 'import_sources')
    op.drop_table('import_sources')

    # === Drop google_credentials table ===
    op.drop_table('google_credentials')

    # === Drop import_profiles table ===
    op.drop_table('import_profiles')
