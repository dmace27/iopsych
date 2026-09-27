"""Add secure candidate invitations and terminal consent records.

Revision ID: 20260927_0004
Revises: 20260927_0003
Create Date: 2026-09-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260927_0004"
down_revision: str | None = "20260927_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create invite and consent tables without ever allocating raw-token storage."""

    op.create_table(
        "assessment_invites",
        sa.Column("role_profile_id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('pending_delivery', 'active', 'consented', 'declined', "
            "'revoked', 'expired')",
            name="assessment_invite_status",
        ),
        sa.ForeignKeyConstraint(["revoked_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["role_profile_id"], ["role_profiles.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_assessment_invites_token_hash"),
    )
    op.create_index("ix_assessment_invites_profile_id", "assessment_invites", ["role_profile_id"])
    op.create_index("ix_assessment_invites_expires_at", "assessment_invites", ["expires_at"])

    op.create_table(
        "candidate_consents",
        sa.Column("invite_id", sa.Uuid(), nullable=False),
        sa.Column("decision", sa.String(length=16), nullable=False),
        sa.Column("notice_version", sa.String(length=80), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("decision IN ('consent', 'decline')", name="consent_decision"),
        sa.ForeignKeyConstraint(["invite_id"], ["assessment_invites.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("invite_id", name="uq_candidate_consents_invite_id"),
    )
    op.create_index("ix_candidate_consents_invite_id", "candidate_consents", ["invite_id"])


def downgrade() -> None:
    """Remove package 2B tables in dependency order."""

    op.drop_index("ix_candidate_consents_invite_id", table_name="candidate_consents")
    op.drop_table("candidate_consents")
    op.drop_index("ix_assessment_invites_expires_at", table_name="assessment_invites")
    op.drop_index("ix_assessment_invites_profile_id", table_name="assessment_invites")
    op.drop_table("assessment_invites")
