"""Preserve structured-extraction assumptions with profile versions.

Revision ID: 20260928_0006
Revises: 20260927_0005
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260928_0006"
down_revision: str | None = "20260927_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add a non-null JSON list and backfill existing manual profiles."""

    op.add_column(
        "role_profiles",
        sa.Column(
            "assumptions_json",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
    )


def downgrade() -> None:
    """Remove extraction assumptions while retaining profile snapshots."""

    op.drop_column("role_profiles", "assumptions_json")
