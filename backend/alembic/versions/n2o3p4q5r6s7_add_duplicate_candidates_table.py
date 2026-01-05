"""Add duplicate_candidates table for deduplication (DEC-041).

Revision ID: n2o3p4q5r6s7
Revises: m1n2o3p4q5r6
Create Date: 2026-01-05 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "n2o3p4q5r6s7"
down_revision: Union[str, None] = "m1n2o3p4q5r6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create duplicate_candidates table for tracking potential duplicates."""
    op.create_table(
        "duplicate_candidates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "design_id",
            sa.String(36),
            sa.ForeignKey("designs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "candidate_design_id",
            sa.String(36),
            sa.ForeignKey("designs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "match_type",
            sa.Enum(
                "HASH",
                "THANGS_ID",
                "TITLE_DESIGNER",
                "FILENAME_SIZE",
                name="duplicatematchtype",
            ),
            nullable=False,
        ),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column(
            "status",
            sa.Enum("PENDING", "MERGED", "REJECTED", name="duplicatecandidatestatus"),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Create indexes for efficient queries
    op.create_index(
        "ix_duplicate_candidates_design_id",
        "duplicate_candidates",
        ["design_id"],
    )
    op.create_index(
        "ix_duplicate_candidates_candidate_design_id",
        "duplicate_candidates",
        ["candidate_design_id"],
    )
    op.create_index(
        "ix_duplicate_candidates_status",
        "duplicate_candidates",
        ["status"],
    )
    op.create_index(
        "ix_duplicate_candidates_match_type_confidence",
        "duplicate_candidates",
        ["match_type", "confidence"],
    )


def downgrade() -> None:
    """Remove duplicate_candidates table."""
    op.drop_index("ix_duplicate_candidates_match_type_confidence", "duplicate_candidates")
    op.drop_index("ix_duplicate_candidates_status", "duplicate_candidates")
    op.drop_index("ix_duplicate_candidates_candidate_design_id", "duplicate_candidates")
    op.drop_index("ix_duplicate_candidates_design_id", "duplicate_candidates")
    op.drop_table("duplicate_candidates")

    # Drop the enum types
    op.execute("DROP TYPE IF EXISTS duplicatematchtype")
    op.execute("DROP TYPE IF EXISTS duplicatecandidatestatus")
