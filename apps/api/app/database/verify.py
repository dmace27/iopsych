"""Post-migration verification for seed completeness and tenant isolation."""

from sqlalchemy.orm import Session

from app.database.repositories import OrganizationDataAccess
from app.database.seed import (
    ALPHA_AUDIT_EVENT_ID,
    ALPHA_ORGANIZATION_ID,
    ALPHA_PROFILE_ID,
    ALPHA_ROLE_ID,
    ALPHA_USER_ID,
    BEACON_AUDIT_EVENT_ID,
    BEACON_ORGANIZATION_ID,
    BEACON_PROFILE_ID,
    BEACON_ROLE_ID,
    BEACON_USER_ID,
)
from app.database.session import create_database_engine, create_session_factory
from iopsych_contracts import ConstructKey


def verify_tenant_isolation(session: Session) -> None:
    """Fail unless both seed tenants can read only their own records."""

    alpha = OrganizationDataAccess(session, ALPHA_ORGANIZATION_ID)
    beacon = OrganizationDataAccess(session, BEACON_ORGANIZATION_ID)

    assert [user.id for user in alpha.list_users()] == [ALPHA_USER_ID]
    assert [user.id for user in beacon.list_users()] == [BEACON_USER_ID]
    assert [role.id for role in alpha.list_roles()] == [ALPHA_ROLE_ID]
    assert [role.id for role in beacon.list_roles()] == [BEACON_ROLE_ID]
    assert [event.id for event in alpha.list_audit_events()] == [ALPHA_AUDIT_EVENT_ID]
    assert [event.id for event in beacon.list_audit_events()] == [BEACON_AUDIT_EVENT_ID]

    # ID knowledge alone must never cross the organization boundary.
    assert alpha.get_user(BEACON_USER_ID) is None
    assert beacon.get_user(ALPHA_USER_ID) is None
    assert alpha.get_role(BEACON_ROLE_ID) is None
    assert beacon.get_role(ALPHA_ROLE_ID) is None
    assert alpha.get_role_profile(BEACON_PROFILE_ID) is None
    assert beacon.get_role_profile(ALPHA_PROFILE_ID) is None
    assert alpha.get_role_construct_rating(ALPHA_PROFILE_ID, ConstructKey.AUTONOMY) is not None
    assert beacon.get_role_construct_rating(BEACON_PROFILE_ID, ConstructKey.AUTONOMY) is not None
    assert alpha.get_role_construct_rating(BEACON_PROFILE_ID, ConstructKey.AUTONOMY) is None
    assert beacon.get_role_construct_rating(ALPHA_PROFILE_ID, ConstructKey.AUTONOMY) is None


def main() -> None:
    """Verify the configured database from CI or a developer shell."""

    engine = create_database_engine()
    factory = create_session_factory(engine)
    with factory() as session:
        verify_tenant_isolation(session)
    engine.dispose()
    print("Database verification passed for two isolated organizations.")


if __name__ == "__main__":  # pragma: no cover - exercised through the documented CLI.
    main()
