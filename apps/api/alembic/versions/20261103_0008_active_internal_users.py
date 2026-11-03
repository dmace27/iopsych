"""Add an explicit account deactivation state without changing existing access.

Revision ID: 20261103_0008
Revises: 20260929_0007
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261103_0008"
down_revision: str | None = "20260929_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Backfill existing users as active before enforcing non-nullability."""

    op.add_column(
        "users", sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False)
    )


def downgrade() -> None:
    """Remove only the new account lifecycle flag."""

    op.drop_column("users", "is_active")
