"""Add encrypted invitation delivery and deduplicated webhook metadata.

Revision ID: 20261104_0012
Revises: 20261104_0011
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261104_0012"
down_revision: str | None = "20261104_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add a separate outbox without changing existing invite validity or consent."""
    op.create_table(
        "provider_invitation_deliveries",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("invite_id", sa.Uuid(), sa.ForeignKey("assessment_invites.id"), nullable=False),
        sa.Column("requested_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("replaces_invite_id", sa.Uuid(), sa.ForeignKey("assessment_invites.id")),
        sa.Column("encrypted_message", sa.Text()),
        sa.Column(
            "status",
            sa.Enum(
                "queued",
                "retrying",
                "sent",
                "delivered",
                "failed",
                "bounced",
                "complained",
                "reissue_required",
                "cancelled",
                name="invitation_delivery_status",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("retry_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("provider_message_id", sa.String(255)),
        sa.Column("last_error_code", sa.String(40)),
        sa.UniqueConstraint("organization_id", "request_id", name="uq_invitation_delivery_request"),
        sa.UniqueConstraint("invite_id", name="uq_invitation_delivery_invite"),
        sa.UniqueConstraint("provider_message_id", name="uq_invitation_delivery_provider_message"),
    )
    op.create_index(
        "ix_provider_invitation_deliveries_due",
        "provider_invitation_deliveries",
        ["status", "next_attempt_at"],
    )
    op.create_table(
        "provider_invitation_delivery_events",
        sa.Column("provider_event_id", sa.String(255), primary_key=True),
        sa.Column(
            "delivery_id",
            sa.Uuid(),
            sa.ForeignKey("provider_invitation_deliveries.id"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    """Remove only delivery state; downgrade discards queued messages and event deduplication."""
    pending = op.get_bind().scalar(
        sa.text(
            "SELECT count(*) FROM provider_invitation_deliveries WHERE status IN ('queued', 'retrying')"
        )
    )
    if pending:
        raise RuntimeError("Cancel pending provider deliveries before downgrade")
    op.drop_table("provider_invitation_delivery_events")
    op.drop_index(
        "ix_provider_invitation_deliveries_due", table_name="provider_invitation_deliveries"
    )
    op.drop_table("provider_invitation_deliveries")
