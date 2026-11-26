"""Add unique constraint on product name (case-insensitive)

Revision ID: a1b2c3d4e5f6
Revises: ebc23833c444
Create Date: 2026-11-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "ebc23833c444"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add case-insensitive unique constraint on product name.

    Before adding the constraint, check for existing duplicates.
    If duplicates exist, raise an error so they can be resolved manually.
    The constraint uses a unique index on lower(name) for case-insensitive
    uniqueness (e.g., "Rice" and "rice" are treated as duplicates).
    """
    conn = op.get_bind()

    # Check for existing duplicate names (case-insensitive, trimmed).
    # Matches the application's normalization policy: names are trimmed
    # before saving, so we must compare trimmed names too.
    duplicates = conn.execute(
        sa.text("""
            SELECT lower(trim(name)) as lname, count(*) as cnt
            FROM products
            GROUP BY lower(trim(name))
            HAVING count(*) > 1
        """)
    ).fetchall()

    if duplicates:
        dup_list = ", ".join(
            f"'{d[0]}' ({d[1]} occurrences)" for d in duplicates
        )
        raise RuntimeError(
            "Cannot add unique constraint: duplicate product names exist: "
            + dup_list
        )

    # Create unique index on lower(trim(name)) for case-insensitive,
    # trimmed uniqueness. Matches application normalization policy.
    op.execute(
        "CREATE UNIQUE INDEX idx_products_name_lower ON products (lower(trim(name)))"
    )


def downgrade() -> None:
    """Remove the case-insensitive unique constraint on product name."""
    op.execute("DROP INDEX IF EXISTS idx_products_name_lower")
