"""Fix design import_source_id foreign key to SET NULL on delete.

Revision ID: m1n2o3p4q5r6
Revises: l0m1n2o3p4q5
Create Date: 2026-01-05 02:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "m1n2o3p4q5r6"
down_revision: Union[str, None] = "l0m1n2o3p4q5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Fix the foreign key constraint to use SET NULL on delete."""
    # Drop the existing constraint
    op.drop_constraint("fk_designs_import_source_id", "designs", type_="foreignkey")

    # Recreate with ondelete SET NULL
    op.create_foreign_key(
        "fk_designs_import_source_id",
        "designs",
        "import_sources",
        ["import_source_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """Revert to the original constraint without ondelete."""
    op.drop_constraint("fk_designs_import_source_id", "designs", type_="foreignkey")

    op.create_foreign_key(
        "fk_designs_import_source_id",
        "designs",
        "import_sources",
        ["import_source_id"],
        ["id"],
    )
