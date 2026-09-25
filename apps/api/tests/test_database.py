"""Database convention, seed, and tenant-isolation tests."""

from datetime import UTC, datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.base import UtcDateTime
from app.database.config import DatabaseSettings
from app.database.models import Organization, RoleConstructRating
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
    SEED_SUMMARY,
    seed_database,
)
from app.database.session import (
    create_database_engine,
    create_session_factory,
    session_scope,
)
from app.database.verify import verify_tenant_isolation
from iopsych_contracts import ConstructKey


def test_seed_is_complete_idempotent_and_synthetic(seeded_session: Session) -> None:
    """The seed can be rerun without duplicates and never contains real email domains."""

    assert seed_database(seeded_session) == SEED_SUMMARY
    seeded_session.commit()

    assert seeded_session.scalar(select(func.count()).select_from(Organization)) == 2
    alpha = OrganizationDataAccess(seeded_session, ALPHA_ORGANIZATION_ID)
    beacon = OrganizationDataAccess(seeded_session, BEACON_ORGANIZATION_ID)
    assert alpha.list_users()[0].email.endswith(".example.invalid")
    assert beacon.list_users()[0].email.endswith(".example.invalid")
    assert alpha.get_role_profile(ALPHA_PROFILE_ID) is not None


def test_organization_scoped_reads_reject_cross_tenant_ids(seeded_session: Session) -> None:
    """Knowing another tenant's UUID must not grant access to any entity layer."""

    alpha = OrganizationDataAccess(seeded_session, ALPHA_ORGANIZATION_ID)
    beacon = OrganizationDataAccess(seeded_session, BEACON_ORGANIZATION_ID)

    assert [user.id for user in alpha.list_users()] == [ALPHA_USER_ID]
    assert [user.id for user in beacon.list_users()] == [BEACON_USER_ID]
    assert alpha.get_user(ALPHA_USER_ID) is not None
    assert alpha.get_user(BEACON_USER_ID) is None
    assert beacon.get_user(ALPHA_USER_ID) is None

    assert [role.id for role in alpha.list_roles()] == [ALPHA_ROLE_ID]
    assert [role.id for role in beacon.list_roles()] == [BEACON_ROLE_ID]
    assert alpha.get_role(ALPHA_ROLE_ID) is not None
    assert alpha.get_role(BEACON_ROLE_ID) is None
    assert beacon.get_role(ALPHA_ROLE_ID) is None

    assert alpha.get_role_profile(ALPHA_PROFILE_ID) is not None
    assert alpha.get_role_profile(BEACON_PROFILE_ID) is None
    assert beacon.get_role_profile(ALPHA_PROFILE_ID) is None

    assert alpha.get_role_construct_rating(ALPHA_PROFILE_ID, ConstructKey.AUTONOMY) is not None
    assert alpha.get_role_construct_rating(BEACON_PROFILE_ID, ConstructKey.AUTONOMY) is None
    assert beacon.get_role_construct_rating(ALPHA_PROFILE_ID, ConstructKey.AUTONOMY) is None

    assert [event.id for event in alpha.list_audit_events()] == [ALPHA_AUDIT_EVENT_ID]
    assert [event.id for event in beacon.list_audit_events()] == [BEACON_AUDIT_EVENT_ID]
    verify_tenant_isolation(seeded_session)


def test_database_rejects_out_of_range_construct_rating(seeded_session: Session) -> None:
    """The 1-5 construct scale is protected below the validation layer."""

    rating = seeded_session.get(RoleConstructRating, (ALPHA_PROFILE_ID, ConstructKey.AUTONOMY))
    assert rating is not None
    rating.rating = 6
    with pytest.raises(IntegrityError):
        seeded_session.commit()
    seeded_session.rollback()


def test_utc_type_rejects_naive_values_and_normalizes_results(database_engine: Engine) -> None:
    """All timestamp writes and reads follow the UTC convention."""

    utc_type = UtcDateTime()
    dialect = database_engine.dialect
    plus_two = timezone(timedelta(hours=2))
    aware = datetime(2026, 1, 1, 14, tzinfo=plus_two)
    naive = datetime(2026, 1, 1, 12)

    assert utc_type.process_bind_param(None, dialect) is None
    assert utc_type.process_result_value(None, dialect) is None
    assert utc_type.process_bind_param(aware, dialect) == datetime(2026, 1, 1, 12, tzinfo=UTC)
    assert utc_type.process_result_value(aware, dialect) == datetime(2026, 1, 1, 12, tzinfo=UTC)
    assert utc_type.process_result_value(naive, dialect) == datetime(2026, 1, 1, 12, tzinfo=UTC)
    with pytest.raises(ValueError, match="timezone-aware"):
        utc_type.process_bind_param(naive, dialect)


def test_engine_configuration_handles_sqlite_and_pooled_databases() -> None:
    """SQLite omits queue-pool settings while PostgreSQL receives the configured size."""

    sqlite_engine = create_database_engine(
        DatabaseSettings(database_url="sqlite+pysqlite:///:memory:", database_echo=True)
    )
    assert sqlite_engine.echo is True
    sqlite_engine.dispose()

    fake_engine = MagicMock(spec=Engine)
    with patch("app.database.session.create_engine", return_value=fake_engine) as create:
        engine = create_database_engine(
            DatabaseSettings(
                database_url="postgresql+psycopg://user:pass@localhost/example",
                database_pool_size=7,
            )
        )
    assert engine is fake_engine
    assert create.call_args.kwargs["pool_size"] == 7
    assert create.call_args.kwargs["pool_pre_ping"] is True


def test_session_scope_commits_and_rolls_back(database_engine: Engine) -> None:
    """The transaction helper commits success and rolls back exceptions."""

    factory = create_session_factory(database_engine)
    organization = Organization(slug="scope-test", name="Scope Test")
    with session_scope(factory) as session:
        session.add(organization)

    with factory() as session:
        assert session.get(Organization, organization.id) is not None

    with pytest.raises(RuntimeError, match="rollback"), session_scope(factory) as session:
        session.add(Organization(slug="rolled-back", name="Rolled Back"))
        raise RuntimeError("rollback")

    with factory() as session:
        statement = select(Organization).where(Organization.slug == "rolled-back")
        assert session.scalar(statement) is None
