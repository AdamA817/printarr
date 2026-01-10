"""Add design families for variant grouping.

Revision ID: y3z4a5b6c7d8
Revises: x2y3z4a5b6c7
Create Date: 2026-01-09 00:00:00.000000

Issue #254: Add design families feature (DEC-044).

This migration:
1. Creates the design_families table for grouping related design variants
2. Creates the family_tags table for family-level tag associations
3. Adds FamilyDetectionMethod enum
4. Adds DETECT_FAMILY_OVERLAP to JobType enum
5. Adds family_id and variant_name columns to designs table
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "y3z4a5b6c7d8"
down_revision: str | None = "x2y3z4a5b6c7"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    """Add design families feature."""
    bind = op.get_bind()
    dialect = bind.dialect.name

    # 1. Create FamilyDetectionMethod enum (PostgreSQL only)
    if dialect == "postgresql":
        # Use DO block to check if type exists before creating
        op.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'familydetectionmethod') THEN
                    CREATE TYPE familydetectionmethod AS ENUM
                        ('NAME_PATTERN', 'FILE_HASH_OVERLAP', 'AI_DETECTED', 'MANUAL');
                END IF;
            END
            $$;
        """)
        # Add DETECT_FAMILY_OVERLAP to jobtype enum
        op.execute("ALTER TYPE jobtype ADD VALUE IF NOT EXISTS 'DETECT_FAMILY_OVERLAP'")

    # 2. Create design_families table
    # Use VARCHAR for detection_method to avoid SQLAlchemy trying to create the enum
    # The enum constraint is enforced by PostgreSQL via the type we created above
    if dialect == "postgresql":
        detection_method_col = sa.Column(
            "detection_method",
            sa.VARCHAR(32),
            nullable=False,
            server_default="MANUAL",
        )
    else:
        detection_method_col = sa.Column(
            "detection_method",
            sa.String(32),
            nullable=False,
            server_default="MANUAL",
        )

    op.create_table(
        "design_families",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("canonical_name", sa.String(512), nullable=False),
        sa.Column("canonical_designer", sa.String(255), nullable=False, server_default="Unknown"),
        sa.Column("name_override", sa.String(512), nullable=True),
        sa.Column("designer_override", sa.String(255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        detection_method_col,
        sa.Column("detection_confidence", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # For PostgreSQL, alter the column to use the enum type
    if dialect == "postgresql":
        # Drop default, alter type, re-add default
        op.execute("ALTER TABLE design_families ALTER COLUMN detection_method DROP DEFAULT")
        op.execute(
            "ALTER TABLE design_families "
            "ALTER COLUMN detection_method TYPE familydetectionmethod "
            "USING detection_method::familydetectionmethod"
        )
        op.execute("ALTER TABLE design_families ALTER COLUMN detection_method SET DEFAULT 'MANUAL'")
    # Create indexes
    op.create_index("ix_design_families_canonical_name", "design_families", ["canonical_name"])
    op.create_index("ix_design_families_canonical_designer", "design_families", ["canonical_designer"])
    op.create_index("ix_design_families_detection_method", "design_families", ["detection_method"])
    op.create_index("ix_design_families_created_at", "design_families", ["created_at"])

    # 3. Create family_tags table
    # Use VARCHAR for source to avoid SQLAlchemy enum creation issues
    op.create_table(
        "family_tags",
        sa.Column("family_id", sa.String(36), nullable=False),
        sa.Column("tag_id", sa.String(36), nullable=False),
        sa.Column("source", sa.String(32), nullable=False, server_default="USER"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("family_id", "tag_id"),
        sa.ForeignKeyConstraint(
            ["family_id"],
            ["design_families.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tag_id"],
            ["tags.id"],
            ondelete="CASCADE",
        ),
    )

    # For PostgreSQL, alter the column to use the existing tagsource enum
    if dialect == "postgresql":
        # Drop default, alter type, re-add default
        op.execute("ALTER TABLE family_tags ALTER COLUMN source DROP DEFAULT")
        op.execute(
            "ALTER TABLE family_tags "
            "ALTER COLUMN source TYPE tagsource "
            "USING source::tagsource"
        )
        op.execute("ALTER TABLE family_tags ALTER COLUMN source SET DEFAULT 'USER'")
    # Create indexes
    op.create_index("ix_family_tags_family_id", "family_tags", ["family_id"])
    op.create_index("ix_family_tags_tag_id", "family_tags", ["tag_id"])

    # 4. Add family_id and variant_name to designs table
    if dialect == "sqlite":
        with op.batch_alter_table("designs", schema=None) as batch_op:
            batch_op.add_column(sa.Column("family_id", sa.String(36), nullable=True))
            batch_op.add_column(sa.Column("variant_name", sa.String(255), nullable=True))
            batch_op.create_foreign_key(
                "fk_designs_family_id",
                "design_families",
                ["family_id"],
                ["id"],
                ondelete="SET NULL",
            )
            batch_op.create_index("ix_designs_family_id", ["family_id"])
    else:
        op.add_column("designs", sa.Column("family_id", sa.String(36), nullable=True))
        op.add_column("designs", sa.Column("variant_name", sa.String(255), nullable=True))
        op.create_foreign_key(
            "fk_designs_family_id",
            "designs",
            "design_families",
            ["family_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index("ix_designs_family_id", "designs", ["family_id"])


def downgrade() -> None:
    """Remove design families feature."""
    bind = op.get_bind()
    dialect = bind.dialect.name

    # 4. Remove family_id and variant_name from designs table
    if dialect == "sqlite":
        with op.batch_alter_table("designs", schema=None) as batch_op:
            batch_op.drop_index("ix_designs_family_id")
            batch_op.drop_constraint("fk_designs_family_id", type_="foreignkey")
            batch_op.drop_column("variant_name")
            batch_op.drop_column("family_id")
    else:
        op.drop_index("ix_designs_family_id", "designs")
        op.drop_constraint("fk_designs_family_id", "designs", type_="foreignkey")
        op.drop_column("designs", "variant_name")
        op.drop_column("designs", "family_id")

    # 3. Drop family_tags table
    op.drop_index("ix_family_tags_tag_id", "family_tags")
    op.drop_index("ix_family_tags_family_id", "family_tags")
    op.drop_table("family_tags")

    # 2. Drop design_families table
    op.drop_index("ix_design_families_created_at", "design_families")
    op.drop_index("ix_design_families_detection_method", "design_families")
    op.drop_index("ix_design_families_canonical_designer", "design_families")
    op.drop_index("ix_design_families_canonical_name", "design_families")
    op.drop_table("design_families")

    # 1. Drop FamilyDetectionMethod enum (PostgreSQL only)
    # Note: Cannot remove enum values in PostgreSQL, leaving type in place
    if dialect == "postgresql":
        op.execute("DROP TYPE IF EXISTS familydetectionmethod")
