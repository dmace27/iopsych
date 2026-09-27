"""Add stable authentication-provider subjects to internal users.

Revision ID: 20260926_0002
Revises: 20260925_0001
Create Date: 2026-09-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260926_0002"
down_revision: str | None = "20260925_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add and backfill the provider subject used for authentication lookup."""

    # Existing package-0C users are mapped to their UUID text. Deployments can
    # replace those values with provider subjects before issuing login tokens.
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("auth_subject", sa.String(length=255), nullable=True))
    op.execute(sa.text("UPDATE users SET auth_subject = CAST(id AS VARCHAR(255))"))
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column("auth_subject", existing_type=sa.String(length=255), nullable=False)
        batch_op.create_unique_constraint("uq_users_auth_subject", ["auth_subject"])


def downgrade() -> None:
    """Remove authentication-provider subjects from internal users."""

    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("uq_users_auth_subject", type_="unique")
        batch_op.drop_column("auth_subject")
