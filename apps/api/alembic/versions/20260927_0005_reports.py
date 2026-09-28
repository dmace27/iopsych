"""Persist submitted assessments and versioned report snapshots.

Revision ID: 20260927_0005
Revises: 20260927_0004
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260927_0005"
down_revision: str | None = "20260927_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create only the submission/report tables introduced by this package."""

    op.create_table(
        "assessments",
        sa.Column("invite_id", sa.Uuid(), nullable=False),
        sa.Column("consent_id", sa.Uuid(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("definition_json", sa.JSON(), nullable=False),
        sa.Column("responses_json", sa.JSON(), nullable=False),
        sa.Column("scores_json", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["invite_id"], ["assessment_invites.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["consent_id"], ["candidate_consents.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("invite_id"),
    )
    op.create_table(
        "alignment_reports",
        sa.Column("assessment_id", sa.Uuid(), nullable=False),
        sa.Column("role_profile_id", sa.Uuid(), nullable=False),
        sa.Column("algorithm_version", sa.String(80), nullable=False),
        sa.Column("result_json", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["assessment_id"], ["assessments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["role_profile_id"], ["role_profiles.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint(
            "assessment_id",
            "role_profile_id",
            "algorithm_version",
            name="uq_alignment_reports_inputs",
        ),
    )
    op.create_table(
        "alignment_items",
        sa.Column("report_id", sa.Uuid(), nullable=False),
        sa.Column("construct_key", sa.String(32), nullable=False),
        sa.Column("classification", sa.String(32), nullable=False),
        sa.Column("confidence", sa.String(16), nullable=False),
        sa.Column("explanation_json", sa.JSON(), nullable=False),
        sa.Column("questions_json", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("report_id", "construct_key"),
        sa.ForeignKeyConstraint(["report_id"], ["alignment_reports.id"], ondelete="RESTRICT"),
    )


def downgrade() -> None:
    """Drop reports before their source submissions."""

    op.drop_table("alignment_items")
    op.drop_table("alignment_reports")
    op.drop_table("assessments")
