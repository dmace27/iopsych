"""Add opt-in local encrypted invitation queue, leaving synchronous rows unchanged.

Revision ID: 20261104_0009
Revises: 20261104_0008
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261104_0009"
down_revision: str | None = "20261104_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "invitation_deliveries",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "organization_id",
            sa.Uuid(),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "invite_id",
            sa.Uuid(),
            sa.ForeignKey("assessment_invites.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("idempotency_digest", sa.String(64), nullable=False),
        sa.Column("request_digest", sa.String(64), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("credential_ciphertext", sa.LargeBinary(), nullable=True),
        sa.Column("credential_key_id", sa.String(80), nullable=True),
        sa.Column("credential_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempt_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("invite_id", name="uq_invitation_deliveries_invite"),
        sa.UniqueConstraint(
            "organization_id", "idempotency_digest", name="uq_delivery_idempotency"
        ),
        sa.CheckConstraint("attempt_count >= 0", name="ck_delivery_attempt_count"),
        sa.CheckConstraint(
            "state IN ('queued', 'sending', 'sent', 'uncertain', 'cancelled', 'expired')",
            name="invitation_delivery_state",
        ),
        sa.CheckConstraint(
            "(state IN ('queued', 'sending') AND credential_ciphertext IS NOT NULL "
            "AND credential_key_id IS NOT NULL) OR "
            "(state NOT IN ('queued', 'sending') AND credential_ciphertext IS NULL "
            "AND credential_key_id IS NULL)",
            name="ck_delivery_credentials",
        ),
    )
    op.create_index(
        "ix_delivery_state_expiry", "invitation_deliveries", ["state", "credential_expires_at"]
    )


def downgrade() -> None:
    # Never silently discard recoverable credentials on downgrade.
    count = op.get_bind().scalar(
        sa.text("SELECT count(*) FROM invitation_deliveries WHERE state IN ('queued', 'sending')")
    )
    if count:
        raise RuntimeError("Cancel or expire pending invitation deliveries before downgrade")
    op.drop_table("invitation_deliveries")
