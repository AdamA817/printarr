"""add_google_folder_id_to_import_records

Revision ID: g5j6k7l8m9n0
Revises: f4i5j6k7l8m9
Create Date: 2026-01-02 16:00:00.000000

Add google_folder_id column to import_records for Google Drive auto_import.

This field stores the Google Drive folder ID for designs detected from
Google Drive sources, enabling file download during auto_import.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'g5j6k7l8m9n0'
down_revision: Union[str, Sequence[str], None] = 'f4i5j6k7l8m9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add google_folder_id column to import_records."""
    op.add_column(
        'import_records',
        sa.Column('google_folder_id', sa.String(255), nullable=True)
    )


def downgrade() -> None:
    """Remove google_folder_id column from import_records."""
    op.drop_column('import_records', 'google_folder_id')
