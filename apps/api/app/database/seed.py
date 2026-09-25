"""Deterministic, synthetic development data for two isolated tenants."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final
from uuid import UUID

from sqlalchemy.orm import Session

from app.database.models import (
    AuditEvent,
    InternalUserRole,
    Organization,
    Role,
    RoleConstructRating,
    RoleProfile,
    RoleProfileStatus,
    RoleStatus,
    User,
)
from app.database.session import create_database_engine, create_session_factory, session_scope
from iopsych_contracts import CONSTRUCT_DEFINITIONS, ConfidenceLevel

ALPHA_ORGANIZATION_ID: Final = UUID("00000000-0000-4000-8000-000000000001")
BEACON_ORGANIZATION_ID: Final = UUID("00000000-0000-4000-8000-000000000002")
ALPHA_USER_ID: Final = UUID("00000000-0000-4000-8000-000000000011")
BEACON_USER_ID: Final = UUID("00000000-0000-4000-8000-000000000012")
ALPHA_ROLE_ID: Final = UUID("00000000-0000-4000-8000-000000000021")
BEACON_ROLE_ID: Final = UUID("00000000-0000-4000-8000-000000000022")
ALPHA_PROFILE_ID: Final = UUID("00000000-0000-4000-8000-000000000031")
BEACON_PROFILE_ID: Final = UUID("00000000-0000-4000-8000-000000000032")
ALPHA_AUDIT_EVENT_ID: Final = UUID("00000000-0000-4000-8000-000000000041")
BEACON_AUDIT_EVENT_ID: Final = UUID("00000000-0000-4000-8000-000000000042")

SEED_TIME: Final = datetime(2026, 1, 1, 12, tzinfo=UTC)


@dataclass(frozen=True)
class SeedSummary:
    """Stable record counts produced by the development seed."""

    organizations: int
    users: int
    roles: int
    profiles: int
    ratings: int
    audit_events: int


SEED_SUMMARY: Final = SeedSummary(
    organizations=2,
    users=2,
    roles=2,
    profiles=2,
    ratings=12,
    audit_events=2,
)


def _ratings(profile_id: UUID, offset: int) -> list[RoleConstructRating]:
    """Build all six ratings with traceable, specification-safe evidence."""

    ratings: list[RoleConstructRating] = []
    for index, definition in enumerate(CONSTRUCT_DEFINITIONS):
        rating = ((index + offset) % 5) + 1
        ratings.append(
            RoleConstructRating(
                profile_id=profile_id,
                construct_key=definition.key,
                rating=rating,
                confidence=ConfidenceLevel.MEDIUM,
                rationale=f"Synthetic seed rationale for {definition.label}.",
                evidence_json=[f"Synthetic job-description evidence for {definition.label}."],
            )
        )
    return ratings


def seed_database(session: Session) -> SeedSummary:
    """Upsert deterministic development records and leave commit control to the caller."""

    records: list[object] = [
        Organization(
            id=ALPHA_ORGANIZATION_ID,
            slug="alpha-labs",
            name="Alpha Labs (Synthetic)",
            created_at=SEED_TIME,
        ),
        Organization(
            id=BEACON_ORGANIZATION_ID,
            slug="beacon-works",
            name="Beacon Works (Synthetic)",
            created_at=SEED_TIME,
        ),
    ]
    for record in records:
        session.merge(record)
    session.flush()

    users = [
        User(
            id=ALPHA_USER_ID,
            organization_id=ALPHA_ORGANIZATION_ID,
            email="recruiter@alpha.example.invalid",
            name="Alpha Recruiter",
            role=InternalUserRole.RECRUITER,
            created_at=SEED_TIME,
        ),
        User(
            id=BEACON_USER_ID,
            organization_id=BEACON_ORGANIZATION_ID,
            email="manager@beacon.example.invalid",
            name="Beacon Manager",
            role=InternalUserRole.HIRING_MANAGER,
            created_at=SEED_TIME,
        ),
    ]
    for user in users:
        session.merge(user)
    session.flush()

    roles = [
        Role(
            id=ALPHA_ROLE_ID,
            organization_id=ALPHA_ORGANIZATION_ID,
            title="Synthetic Platform Engineer",
            department="Engineering",
            location="Remote",
            job_description="Synthetic role data for local development only.",
            status=RoleStatus.ACTIVE,
            created_at=SEED_TIME,
        ),
        Role(
            id=BEACON_ROLE_ID,
            organization_id=BEACON_ORGANIZATION_ID,
            title="Synthetic Program Lead",
            department="Operations",
            location="Hybrid",
            job_description="Synthetic role data for local development only.",
            status=RoleStatus.ACTIVE,
            created_at=SEED_TIME,
        ),
    ]
    for role in roles:
        session.merge(role)
    session.flush()

    profiles = [
        RoleProfile(
            id=ALPHA_PROFILE_ID,
            role_id=ALPHA_ROLE_ID,
            version=1,
            status=RoleProfileStatus.APPROVED,
            created_by=ALPHA_USER_ID,
            approved_by=ALPHA_USER_ID,
            approved_at=SEED_TIME,
            created_at=SEED_TIME,
        ),
        RoleProfile(
            id=BEACON_PROFILE_ID,
            role_id=BEACON_ROLE_ID,
            version=1,
            status=RoleProfileStatus.APPROVED,
            created_by=BEACON_USER_ID,
            approved_by=BEACON_USER_ID,
            approved_at=SEED_TIME,
            created_at=SEED_TIME,
        ),
    ]
    for profile in profiles:
        session.merge(profile)
    session.flush()

    for rating in [*_ratings(ALPHA_PROFILE_ID, 0), *_ratings(BEACON_PROFILE_ID, 2)]:
        session.merge(rating)

    audit_events = [
        AuditEvent(
            id=ALPHA_AUDIT_EVENT_ID,
            organization_id=ALPHA_ORGANIZATION_ID,
            actor_id=ALPHA_USER_ID,
            event_type="seed.role_profile_created",
            entity_type="role_profile",
            entity_id=ALPHA_PROFILE_ID,
            metadata_json={"source": "synthetic_seed"},
            created_at=SEED_TIME,
        ),
        AuditEvent(
            id=BEACON_AUDIT_EVENT_ID,
            organization_id=BEACON_ORGANIZATION_ID,
            actor_id=BEACON_USER_ID,
            event_type="seed.role_profile_created",
            entity_type="role_profile",
            entity_id=BEACON_PROFILE_ID,
            metadata_json={"source": "synthetic_seed"},
            created_at=SEED_TIME,
        ),
    ]
    for event in audit_events:
        session.merge(event)
    session.flush()
    return SEED_SUMMARY


def main() -> None:
    """Seed the configured database from the command line."""

    engine = create_database_engine()
    factory = create_session_factory(engine)
    with session_scope(factory) as session:
        summary = seed_database(session)
    engine.dispose()
    print(
        "Seed complete: "
        f"{summary.organizations} organizations, {summary.roles} roles, "
        f"{summary.ratings} construct ratings."
    )


if __name__ == "__main__":  # pragma: no cover - exercised through the documented CLI.
    main()
