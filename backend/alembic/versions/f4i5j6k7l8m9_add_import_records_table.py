"""add_import_records_table

Revision ID: f4i5j6k7l8m9
Revises: e3h4i5j6k7l8
Create Date: 2026-01-02 12:00:00.000000

Add v0.8 ImportRecord table for tracking individual imported files/folders.

Features:
- Duplicate detection via source_path and file_hash
- Re-sync detection via file_mtime
- Import history and audit trail

See DEC-037 for conflict handling decisions.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f4i5j6k7l8m9'
down_revision: Union[str, Sequence[str], None] = 'e3h4i5j6k7l8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add import_records table."""
    op.create_table(
        'import_records',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('import_source_id', sa.String(36), nullable=False),
        sa.Column('source_path', sa.String(2048), nullable=False),
        sa.Column('file_hash', sa.String(64), nullable=True),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('file_mtime', sa.DateTime(), nullable=True),
        sa.Column('status', sa.Enum(
            'PENDING', 'IMPORTING', 'IMPORTED', 'SKIPPED', 'ERROR',
            name='importrecordstatus'
        ), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('design_id', sa.String(36), nullable=True),
        sa.Column('detected_title', sa.String(512), nullable=True),
        sa.Column('detected_designer', sa.String(255), nullable=True),
        sa.Column('model_file_count', sa.Integer(), default=0),
        sa.Column('preview_file_count', sa.Integer(), default=0),
        sa.Column('detected_at', sa.DateTime(), nullable=False),
        sa.Column('imported_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(
            ['import_source_id'], ['import_sources.id'],
            ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(
            ['design_id'], ['designs.id'],
            ondelete='SET NULL'
        ),
    )

    # Create indexes
    op.create_index(
        'ix_import_records_source',
        'import_records',
        ['import_source_id']
    )
    op.create_index(
        'ix_import_records_source_path',
        'import_records',
        ['import_source_id', 'source_path'],
        unique=True
    )
    op.create_index(
        'ix_import_records_hash',
        'import_records',
        ['file_hash']
    )
    op.create_index(
        'ix_import_records_status',
        'import_records',
        ['status']
    )
    op.create_index(
        'ix_import_records_design',
        'import_records',
        ['design_id']
    )


def downgrade() -> None:
    """Remove import_records table."""
    op.drop_index('ix_import_records_design', table_name='import_records')
    op.drop_index('ix_import_records_status', table_name='import_records')
    op.drop_index('ix_import_records_hash', table_name='import_records')
    op.drop_index('ix_import_records_source_path', table_name='import_records')
    op.drop_index('ix_import_records_source', table_name='import_records')
    op.drop_table('import_records')
    op.execute("DROP TYPE IF EXISTS importrecordstatus")
