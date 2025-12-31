"""add_discovered_channels_table

Revision ID: b9e6f3a2c5d7
Revises: a8d5f2e1b3c4
Create Date: 2025-12-30 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b9e6f3a2c5d7'
down_revision: Union[str, Sequence[str], None] = 'a8d5f2e1b3c4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create discovered_channels table for tracking channels found via monitored content."""
    op.create_table(
        'discovered_channels',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('telegram_peer_id', sa.String(64), unique=True, nullable=True),
        sa.Column('title', sa.String(255), nullable=True),
        sa.Column('username', sa.String(255), nullable=True),
        sa.Column('invite_hash', sa.String(255), nullable=True),
        sa.Column('is_private', sa.Boolean(), default=False, nullable=False),
        sa.Column('reference_count', sa.Integer(), default=1, nullable=False),
        sa.Column('first_seen_at', sa.DateTime(), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(), nullable=False),
        sa.Column('source_types', sa.JSON(), default=list, nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )

    # Create indexes
    op.create_index(
        'ix_discovered_channels_telegram_peer_id',
        'discovered_channels',
        ['telegram_peer_id']
    )
    op.create_index(
        'ix_discovered_channels_username',
        'discovered_channels',
        ['username']
    )
    op.create_index(
        'ix_discovered_channels_reference_count',
        'discovered_channels',
        ['reference_count']
    )
    op.create_index(
        'ix_discovered_channels_refs_last_seen',
        'discovered_channels',
        ['reference_count', 'last_seen_at']
    )


def downgrade() -> None:
    """Drop discovered_channels table."""
    op.drop_index('ix_discovered_channels_refs_last_seen', 'discovered_channels')
    op.drop_index('ix_discovered_channels_reference_count', 'discovered_channels')
    op.drop_index('ix_discovered_channels_username', 'discovered_channels')
    op.drop_index('ix_discovered_channels_telegram_peer_id', 'discovered_channels')
    op.drop_table('discovered_channels')
