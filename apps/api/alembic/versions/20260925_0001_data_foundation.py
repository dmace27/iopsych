"""Create the package 0C data foundation.

Revision ID: 20260925_0001
Revises: None
Create Date: 2026-09-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260925_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create organizations, users, roles, profiles, ratings, and audit events."""

    op.create_table(
        "organizations",
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_table(
        "users",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "role IN ('admin', 'recruiter', 'hiring_manager')",
            name="internal_user_role",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "email", name="uq_users_organization_email"),
    )
    op.create_index("ix_users_organization_id", "users", ["organization_id"])
    op.create_table(
        "roles",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("department", sa.String(length=160), nullable=False),
        sa.Column("location", sa.String(length=160), nullable=False),
        sa.Column("job_description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("status IN ('draft', 'active', 'archived')", name="role_status"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_roles_organization_id", "roles", ["organization_id"])
    op.create_table(
        "role_profiles",
        sa.Column("role_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("approved_by", sa.Uuid(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("version >= 1", name="ck_role_profiles_version_positive"),
        sa.CheckConstraint(
            "status IN ('draft', 'approved', 'superseded')",
            name="role_profile_status",
        ),
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("role_id", "version", name="uq_role_profiles_role_version"),
    )
    op.create_index("ix_role_profiles_role_id", "role_profiles", ["role_id"])
    op.create_table(
        "role_construct_ratings",
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("construct_key", sa.String(length=32), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("confidence", sa.String(length=16), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("evidence_json", sa.JSON(), nullable=False),
        sa.CheckConstraint(
            "construct_key IN "
            "('autonomy', 'structure', 'ambiguity', 'collaboration', 'mastery', 'pace')",
            name="construct_key",
        ),
        sa.CheckConstraint("confidence IN ('low', 'medium', 'high')", name="confidence_level"),
        sa.CheckConstraint("rating BETWEEN 1 AND 5", name="ck_role_construct_ratings_rating"),
        sa.ForeignKeyConstraint(["profile_id"], ["role_profiles.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("profile_id", "construct_key"),
    )
    op.create_index(
        "ix_role_construct_ratings_profile_id", "role_construct_ratings", ["profile_id"]
    )
    op.create_table(
        "audit_events",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column("entity_type", sa.String(length=120), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_events_actor_id", "audit_events", ["actor_id"])
    op.create_index(
        "ix_audit_events_organization_created",
        "audit_events",
        ["organization_id", "created_at"],
    )


def downgrade() -> None:
    """Remove the foundation tables in reverse dependency order."""

    op.drop_index("ix_audit_events_organization_created", table_name="audit_events")
    op.drop_index("ix_audit_events_actor_id", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index("ix_role_construct_ratings_profile_id", table_name="role_construct_ratings")
    op.drop_table("role_construct_ratings")
    op.drop_index("ix_role_profiles_role_id", table_name="role_profiles")
    op.drop_table("role_profiles")
    op.drop_index("ix_roles_organization_id", table_name="roles")
    op.drop_table("roles")
    op.drop_index("ix_users_organization_id", table_name="users")
    op.drop_table("users")
    op.drop_table("organizations")
