"""Relational foundation from MVP specification section 9."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import (
    DDL,
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
    event,
)
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Mapped, Mapper, mapped_column

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


class AssessmentInviteStatus(StrEnum):
    """Security and consent lifecycle for one candidate invitation."""

    PENDING_DELIVERY = "pending_delivery"
    ACTIVE = "active"
    CONSENTED = "consented"
    DECLINED = "declined"
    REVOKED = "revoked"
    EXPIRED = "expired"


class ConsentDecision(StrEnum):
    """The two explicit choices a candidate can record."""

    CONSENT = "consent"
    DECLINE = "decline"


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
        UniqueConstraint("auth_subject", name="uq_users_auth_subject"),
        Index("ix_users_organization_id", "organization_id"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    # The authentication provider's stable subject is deliberately separate
    # from email, which can change and must never be used as an identity key.
    auth_subject: Mapped[str] = mapped_column(String(255), nullable=False)
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


class AssessmentInvite(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    """An expiring bearer invitation whose raw token is never persisted."""

    __tablename__ = "assessment_invites"
    __table_args__ = (
        Index("ix_assessment_invites_profile_id", "role_profile_id"),
        Index("ix_assessment_invites_expires_at", "expires_at"),
        UniqueConstraint("token_hash", name="uq_assessment_invites_token_hash"),
    )

    role_profile_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("role_profiles.id", ondelete="RESTRICT"),
        nullable=False,
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)
    status: Mapped[AssessmentInviteStatus] = mapped_column(
        enum_type(AssessmentInviteStatus, "assessment_invite_status", 32), nullable=False
    )
    sent_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
    revoked_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )


class CandidateConsent(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    """A terminal affirmative-consent or decline record for one invite."""

    __tablename__ = "candidate_consents"
    __table_args__ = (
        UniqueConstraint("invite_id", name="uq_candidate_consents_invite_id"),
        Index("ix_candidate_consents_invite_id", "invite_id"),
    )

    invite_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("assessment_invites.id", ondelete="RESTRICT"),
        nullable=False,
    )
    decision: Mapped[ConsentDecision] = mapped_column(
        enum_type(ConsentDecision, "consent_decision", 16), nullable=False
    )
    notice_version: Mapped[str] = mapped_column(String(80), nullable=False)


class Assessment(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    """Server-scored, one-time submission tied to an invitation and consent."""

    __tablename__ = "assessments"
    invite_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("assessment_invites.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    consent_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("candidate_consents.id", ondelete="RESTRICT"), nullable=False
    )
    submitted_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
    definition_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    responses_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    scores_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class AlignmentReport(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    """Persisted matching snapshot with authoritative input references."""

    __tablename__ = "alignment_reports"
    __table_args__ = (
        UniqueConstraint(
            "assessment_id",
            "role_profile_id",
            "algorithm_version",
            name="uq_alignment_reports_inputs",
        ),
    )
    assessment_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("assessments.id", ondelete="RESTRICT"), nullable=False
    )
    role_profile_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("role_profiles.id", ondelete="RESTRICT"), nullable=False
    )
    algorithm_version: Mapped[str] = mapped_column(String(80), nullable=False)
    result_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class AlignmentReportItem(Base):
    """One traceable construct item, including question text and stable IDs."""

    __tablename__ = "alignment_items"
    report_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("alignment_reports.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    construct_key: Mapped[str] = mapped_column(String(32), primary_key=True)
    classification: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[str] = mapped_column(String(16), nullable=False)
    explanation_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    questions_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


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


@event.listens_for(AuditEvent, "before_update")
@event.listens_for(AuditEvent, "before_delete")
def prevent_audit_event_mutation(
    mapper: Mapper[AuditEvent],
    connection: Connection,
    target: AuditEvent,
) -> None:
    """Reject ORM updates and deletes so audit records remain append-only."""

    # The arguments are required by SQLAlchemy's mapper-event contract. They
    # are intentionally unused because every mutation is forbidden equally.
    del mapper, connection, target
    raise TypeError("audit events are immutable")


# Database triggers backstop the ORM guard so direct SQL and bulk operations
# cannot rewrite or delete the audit trail. Alembic installs equivalent
# triggers for migrated databases; these listeners protect metadata-created
# databases used by tests and embedded deployments.
event.listen(
    AuditEvent.__table__,
    "after_create",
    DDL(  # type: ignore[no-untyped-call]  # SQLAlchemy omits DDL stub typing.
        "CREATE TRIGGER trg_audit_events_no_update "
        "BEFORE UPDATE ON audit_events BEGIN "
        "SELECT RAISE(ABORT, 'audit events are immutable'); END"
    ).execute_if(dialect="sqlite"),
)
event.listen(
    AuditEvent.__table__,
    "after_create",
    DDL(  # type: ignore[no-untyped-call]  # SQLAlchemy omits DDL stub typing.
        "CREATE TRIGGER trg_audit_events_no_delete "
        "BEFORE DELETE ON audit_events BEGIN "
        "SELECT RAISE(ABORT, 'audit events are immutable'); END"
    ).execute_if(dialect="sqlite"),
)
event.listen(
    AuditEvent.__table__,
    "after_create",
    DDL(  # type: ignore[no-untyped-call]  # SQLAlchemy omits DDL stub typing.
        "CREATE OR REPLACE FUNCTION reject_audit_event_mutation() "
        "RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN "
        "RAISE EXCEPTION 'audit events are immutable'; END; $$"
    ).execute_if(dialect="postgresql"),
)
event.listen(
    AuditEvent.__table__,
    "after_create",
    DDL(  # type: ignore[no-untyped-call]  # SQLAlchemy omits DDL stub typing.
        "CREATE TRIGGER trg_audit_events_no_truncate "
        "BEFORE TRUNCATE ON audit_events FOR EACH STATEMENT "
        "EXECUTE FUNCTION reject_audit_event_mutation()"
    ).execute_if(dialect="postgresql"),
)
event.listen(
    AuditEvent.__table__,
    "after_create",
    DDL(  # type: ignore[no-untyped-call]  # SQLAlchemy omits DDL stub typing.
        "CREATE TRIGGER trg_audit_events_immutable "
        "BEFORE UPDATE OR DELETE ON audit_events FOR EACH ROW "
        "EXECUTE FUNCTION reject_audit_event_mutation()"
    ).execute_if(dialect="postgresql"),
)
