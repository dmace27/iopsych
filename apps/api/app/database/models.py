"""Relational foundation from MVP specification section 9."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, CreatedAtMixin, UtcDateTime, UuidPrimaryKeyMixin
from iopsych_contracts import ConfidenceLevel, ConstructKey


class InternalUserRole(StrEnum):
    """Authorization roles supported by the planned internal workflow."""

    ADMIN = "admin"
    RECRUITER = "recruiter"
    HIRING_MANAGER = "hiring_manager"


class RoleStatus(StrEnum):
    """Lifecycle states for a role record."""

    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class RoleProfileStatus(StrEnum):
    """Lifecycle states for a versioned role profile."""

    DRAFT = "draft"
    APPROVED = "approved"
    SUPERSEDED = "superseded"


def enum_type(enum_class: type[StrEnum], name: str, length: int) -> Enum:
    """Create a portable string enum with a database check constraint."""

    return Enum(
        enum_class,
        name=name,
        native_enum=False,
        create_constraint=True,
        validate_strings=True,
        values_callable=lambda members: [member.value for member in members],
        length=length,
    )


class Organization(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    """A tenant boundary for all internal application data."""

    __tablename__ = "organizations"

    slug: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)


class User(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    """An organization-scoped internal user."""

    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("organization_id", "email", name="uq_users_organization_email"),
        Index("ix_users_organization_id", "organization_id"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    role: Mapped[InternalUserRole] = mapped_column(
        enum_type(InternalUserRole, "internal_user_role", 32), nullable=False
    )


class Role(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    """A job role owned by one organization."""

    __tablename__ = "roles"
    __table_args__ = (Index("ix_roles_organization_id", "organization_id"),)

    organization_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    department: Mapped[str] = mapped_column(String(160), nullable=False)
    location: Mapped[str] = mapped_column(String(160), nullable=False)
    job_description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[RoleStatus] = mapped_column(
        enum_type(RoleStatus, "role_status", 16), nullable=False
    )


class RoleProfile(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    """A versioned snapshot of a role's construct profile."""

    __tablename__ = "role_profiles"
    __table_args__ = (
        UniqueConstraint("role_id", "version", name="uq_role_profiles_role_version"),
        CheckConstraint("version >= 1", name="ck_role_profiles_version_positive"),
        Index("ix_role_profiles_role_id", "role_id"),
    )

    role_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("roles.id", ondelete="RESTRICT"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[RoleProfileStatus] = mapped_column(
        enum_type(RoleProfileStatus, "role_profile_status", 16), nullable=False
    )
    created_by: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    approved_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)


class RoleConstructRating(Base):
    """A behaviorally grounded rating for one construct in one profile."""

    __tablename__ = "role_construct_ratings"
    __table_args__ = (
        CheckConstraint("rating BETWEEN 1 AND 5", name="ck_role_construct_ratings_rating"),
        Index("ix_role_construct_ratings_profile_id", "profile_id"),
    )

    profile_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("role_profiles.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    construct_key: Mapped[ConstructKey] = mapped_column(
        enum_type(ConstructKey, "construct_key", 32), primary_key=True
    )
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence: Mapped[ConfidenceLevel] = mapped_column(
        enum_type(ConfidenceLevel, "confidence_level", 16), nullable=False
    )
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)


class AuditEvent(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    """An organization-scoped record of a sensitive action."""

    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_events_organization_created", "organization_id", "created_at"),
        Index("ix_audit_events_actor_id", "actor_id"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    actor_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(String(120), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(120), nullable=False)
    entity_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
