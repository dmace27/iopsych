"""Preserve existing users while adding explicit access state and versions.

Revision ID: 20261104_0010
Revises: 20261104_0009
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261104_0010"
down_revision: str | None = "20261104_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Keep old accounts enabled and initialize their optimistic version."""

    with op.batch_alter_table("users") as batch:
        batch.add_column(
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true())
        )
        batch.add_column(sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
        batch.create_check_constraint("ck_users_version_positive", "version >= 1")


def downgrade() -> None:
    """Remove access-management fields without modifying historical identities."""

    with op.batch_alter_table("users") as batch:
        batch.drop_constraint("ck_users_version_positive", type_="check")
        batch.drop_column("version")
        batch.drop_column("is_active")
