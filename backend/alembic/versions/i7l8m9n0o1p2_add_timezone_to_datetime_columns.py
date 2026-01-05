"""add_timezone_to_datetime_columns

Revision ID: i7l8m9n0o1p2
Revises: h6k7l8m9n0o1
Create Date: 2026-01-04 10:00:00.000000

Add timezone support to all DateTime columns for PostgreSQL compatibility.

This migration:
1. Alters all TIMESTAMP columns to TIMESTAMP WITH TIME ZONE for PostgreSQL
2. Converts existing UTC timestamps (they were already stored as UTC)
3. No changes needed for SQLite (it stores datetimes as text)

See issue #177 for details.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine import reflection


# revision identifiers, used by Alembic.
revision: str = 'i7l8m9n0o1p2'
down_revision: Union[str, Sequence[str], None] = 'h6k7l8m9n0o1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# All tables and their DateTime columns that need to be updated
DATETIME_COLUMNS = {
    'jobs': ['created_at', 'started_at', 'finished_at'],
    'channels': ['download_mode_enabled_at', 'last_sync_at', 'created_at', 'updated_at'],
    'external_metadata_sources': ['last_fetched_at', 'created_at'],
    'designs': ['created_at', 'updated_at'],
    'attachments': ['created_at'],
    'tags': ['created_at'],
    'preview_assets': ['created_at'],
    'design_sources': ['created_at'],
    'design_files': ['created_at'],
    'telegram_messages': ['date_posted', 'created_at'],
    'import_sources': ['last_sync_at', 'created_at', 'updated_at'],
    'import_profiles': ['created_at', 'updated_at'],
    'design_tags': ['created_at'],
    'app_settings': ['updated_at'],
    'import_source_folders': ['last_synced_at', 'created_at'],
    'google_credentials': ['expires_at', 'created_at', 'updated_at'],
    'import_records': ['file_mtime', 'detected_at', 'imported_at'],
    'discovered_channels': ['first_seen_at', 'last_seen_at', 'created_at', 'updated_at'],
}


def upgrade() -> None:
    """Convert DateTime columns to timezone-aware for PostgreSQL."""
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == 'postgresql':
        # PostgreSQL: ALTER COLUMN TYPE with conversion
        for table, columns in DATETIME_COLUMNS.items():
            # Check if table exists (some tables may not exist in older databases)
            inspector = reflection.Inspector.from_engine(bind)
            if table not in inspector.get_table_names():
                continue

            existing_columns = {col['name'] for col in inspector.get_columns(table)}

            for column in columns:
                if column not in existing_columns:
                    continue

                # Convert TIMESTAMP WITHOUT TIME ZONE to TIMESTAMP WITH TIME ZONE
                # Using 'UTC' since all our datetimes were stored as UTC
                op.execute(
                    sa.text(f"""
                        ALTER TABLE {table}
                        ALTER COLUMN {column}
                        TYPE TIMESTAMP WITH TIME ZONE
                        USING {column} AT TIME ZONE 'UTC'
                    """)
                )
    # SQLite: No changes needed - DateTime columns store text which is timezone-agnostic


def downgrade() -> None:
    """Revert timezone-aware columns back to timezone-naive for PostgreSQL."""
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == 'postgresql':
        for table, columns in DATETIME_COLUMNS.items():
            # Check if table exists
            inspector = reflection.Inspector.from_engine(bind)
            if table not in inspector.get_table_names():
                continue

            existing_columns = {col['name'] for col in inspector.get_columns(table)}

            for column in columns:
                if column not in existing_columns:
                    continue

                # Convert back to TIMESTAMP WITHOUT TIME ZONE
                op.execute(
                    sa.text(f"""
                        ALTER TABLE {table}
                        ALTER COLUMN {column}
                        TYPE TIMESTAMP WITHOUT TIME ZONE
                    """)
                )
    # SQLite: No changes needed
