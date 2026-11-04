"""Fail-closed service boundaries and idempotent defensive rechecks."""

import os
from collections.abc import Generator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI, Request
from sqlalchemy import Engine, create_engine, select
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from app.accounts.schemas import AccountUpdateRequest
from app.accounts.service import discover_accounts, update_account
from app.auth.context import AuthorizationContext, OrganizationScope
from app.auth.dependencies import get_database_session
from app.auth.errors import AccessProblemError
from app.database.base import Base
from app.database.models import Assessment, AuditEvent, InternalUserRole, User
from app.database.seed import (
    ALPHA_ORGANIZATION_ID,
    ALPHA_PROFILE_ID,
    ALPHA_ROLE_ID,
    ALPHA_USER_ID,
    seed_database,
)
from app.database.session import (
    REQUEST_SESSION_STATE_ATTRIBUTE,
    REQUEST_TRANSACTION_INFO_KEY,
    create_session_factory,
)
from app.invitations.queue import local_cipher
from app.invitations.schemas import InvitationCreateRequest
from app.invitations.service import InternalInvitationService
from app.invitations.tokens import InviteTokenCodec
from app.privacy.config import PrivacySettings
from app.privacy.service import PrivacyService
from tests.test_delivery_queue import authentication, settings
from tests.test_invitations import INVITE_SECRET, RecordingDelivery
from tests.test_privacy import candidate_record


def context(role: InternalUserRole = InternalUserRole.ADMIN) -> AuthorizationContext:
    return AuthorizationContext(
        user_id=ALPHA_USER_ID,
        organization=OrganizationScope(ALPHA_ORGANIZATION_ID),
        email="synthetic@example.invalid",
        name="Synthetic actor",
        role=role,
    )


def snapshot(session: Session) -> dict[str, list[dict[str, Any]]]:
    return {
        table.name: [dict(row) for row in session.execute(select(table)).mappings()]
        for table in Base.metadata.sorted_tables
    }


@pytest.mark.parametrize("role", [InternalUserRole.RECRUITER, InternalUserRole.HIRING_MANAGER])
def test_account_discovery_denies_non_admin_without_mutation(
    seeded_session: Session, role: InternalUserRole
) -> None:
    before = snapshot(seeded_session)
    with pytest.raises(AccessProblemError) as error:
        discover_accounts(seeded_session, context(role))
    assert (error.value.status, error.value.code) == (403, "permission_denied")
    assert snapshot(seeded_session) == before
    assert not seeded_session.new and not seeded_session.dirty


@pytest.mark.parametrize("limit", [0, -1, 101])
def test_account_discovery_rejects_invalid_service_limit(
    seeded_session: Session, limit: int
) -> None:
    before = snapshot(seeded_session)
    with pytest.raises(ValueError, match="limit must be between 1 and 100"):
        discover_accounts(seeded_session, context(), limit=limit)
    assert snapshot(seeded_session) == before


def test_account_update_rejects_disappeared_organization(seeded_session: Session) -> None:
    stale_context = replace(context(), organization=OrganizationScope(uuid4()))
    before = snapshot(seeded_session)
    with pytest.raises(AccessProblemError) as error:
        update_account(
            seeded_session,
            stale_context,
            ALPHA_USER_ID,
            AccountUpdateRequest(expected_version=1, is_active=False),
        )
    assert (error.value.status, error.value.code) == (401, "authentication_required")
    assert snapshot(seeded_session) == before


@pytest.mark.parametrize("count", [None, 0, 1])
def test_account_update_fails_closed_on_insufficient_admin_count(
    seeded_session: Session, monkeypatch: pytest.MonkeyPatch, count: int | None
) -> None:
    """Inject only the aggregate result after real actor/target authorization queries."""

    actor = seeded_session.get(User, ALPHA_USER_ID)
    assert actor is not None
    actor.role = InternalUserRole.ADMIN
    target = User(
        organization_id=ALPHA_ORGANIZATION_ID,
        email="second-admin@example.invalid",
        name="Synthetic second admin",
        auth_subject="synthetic-second-admin",
        role=InternalUserRole.ADMIN,
    )
    seeded_session.add(target)
    seeded_session.commit()
    before = snapshot(seeded_session)
    scalar = seeded_session.scalar
    count_queries = []

    def guarded_scalar(statement: Any, *args: Any, **kwargs: Any) -> Any:
        if str(statement).startswith("SELECT count(*)"):
            count_queries.append(statement)
            assert scalar(statement, *args, **kwargs) == 2
            return count
        return scalar(statement, *args, **kwargs)

    monkeypatch.setattr(seeded_session, "scalar", guarded_scalar)
    with pytest.raises(AccessProblemError) as error:
        update_account(
            seeded_session,
            context(),
            target.id,
            AccountUpdateRequest(expected_version=target.version, is_active=False),
        )
    assert (error.value.status, error.value.code) == (409, "last_active_admin")
    assert len(count_queries) == 1
    assert snapshot(seeded_session) == before
    assert not seeded_session.new and not seeded_session.dirty


def test_database_dependency_reuses_middleware_session(seeded_session: Session) -> None:
    app = FastAPI()
    request = Request({"type": "http", "app": app})
    setattr(request.state, REQUEST_SESSION_STATE_ATTRIBUTE, seeded_session)
    seeded_session.info[REQUEST_TRANSACTION_INFO_KEY] = True
    before = snapshot(seeded_session)
    assert list(get_database_session(request)) == [seeded_session]
    assert getattr(request.state, REQUEST_SESSION_STATE_ATTRIBUTE) is seeded_session
    assert seeded_session.info[REQUEST_TRANSACTION_INFO_KEY] is True
    assert seeded_session.is_active
    assert snapshot(seeded_session) == before


@pytest.fixture
def defensive_postgres() -> Generator[Session]:
    raw = os.environ.get("DEFENSIVE_TEST_POSTGRES_URL")
    if raw is None:
        pytest.skip("Set isolated DEFENSIVE_TEST_POSTGRES_URL for queue defensive checks")
    url = make_url(raw)
    assert url.host == "127.0.0.1" and url.port == 5604
    assert url.database == "iopsych_defensive" and url.username == "synthetic"
    schema = f"defensive_{uuid4().hex}"
    admin = create_engine(url)
    with admin.begin() as connection:
        connection.execute(CreateSchema(schema))
    engine = create_engine(url.update_query_dict({"options": f"-csearch_path={schema}"}))
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            seed_database(session)
            session.commit()
            yield session
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        admin.dispose()


def test_queued_invitation_without_cipher_fails_before_any_write(
    defensive_postgres: Session,
) -> None:
    delivery = RecordingDelivery()
    service = InternalInvitationService(
        defensive_postgres, context(), settings(), InviteTokenCodec(INVITE_SECRET), delivery
    )
    before = snapshot(defensive_postgres)
    with pytest.raises(AccessProblemError) as error:
        service.create(
            ALPHA_ROLE_ID,
            InvitationCreateRequest(role_profile_id=ALPHA_PROFILE_ID, email="one@example.invalid"),
            idempotency_key="synthetic-no-cipher-0001",
        )
    assert (error.value.status, error.value.code) == (503, "invitation_service_unavailable")
    assert snapshot(defensive_postgres) == before
    assert delivery.messages == []
    assert not defensive_postgres.new and not defensive_postgres.dirty


def test_unrelated_queue_integrity_error_is_reraised_without_partial_writes(
    defensive_postgres: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    policy = settings()
    codec = InviteTokenCodec(INVITE_SECRET)
    token = codec.generate()
    monkeypatch.setattr(codec, "generate", lambda: token)
    delivery = RecordingDelivery()
    service = InternalInvitationService(
        defensive_postgres,
        context(),
        policy,
        codec,
        delivery,
        queue_cipher=local_cipher(policy, authentication()),
    )
    first = service.create(
        ALPHA_ROLE_ID,
        InvitationCreateRequest(role_profile_id=ALPHA_PROFILE_ID, email="one@example.invalid"),
        idempotency_key="synthetic-collision-0001",
    )
    before = snapshot(defensive_postgres)
    with pytest.raises(IntegrityError) as error:
        service.create(
            ALPHA_ROLE_ID,
            InvitationCreateRequest(role_profile_id=ALPHA_PROFILE_ID, email="two@example.invalid"),
            idempotency_key="synthetic-collision-0002",
        )
    assert "token_hash" in str(error.value.orig)
    assert snapshot(defensive_postgres) == before
    assert defensive_postgres.is_active
    assert delivery.messages == []
    assert first.token_hash == token.token_hash


def test_retention_does_not_recount_record_anonymized_after_selection(
    seeded_session: Session, database_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Inject a completed real anonymization at the selected-record recheck boundary."""

    now = datetime.now(UTC)
    factory = create_session_factory(database_engine)
    assessment_id, _ = candidate_record(
        factory,
        submitted_at=now - timedelta(days=100),
        retention_expires_at=now - timedelta(days=1),
        with_report=True,
    )
    service = PrivacyService(seeded_session, PrivacySettings(_env_file=None), context())
    get_record = service._get_record
    rechecked = []
    anonymized_snapshots = []

    def anonymize_before_recheck(identifier: UUID, *, lock: bool = False) -> Any:
        rechecked.append(identifier)
        result = PrivacyService(
            seeded_session, PrivacySettings(_env_file=None), context()
        ).anonymize(identifier, now=now)
        assert not result.already_anonymized
        anonymized_snapshots.append(snapshot(seeded_session))
        return get_record(identifier, lock=lock)

    monkeypatch.setattr(service, "_get_record", anonymize_before_recheck)
    result = service.run_retention(now=now)
    assert rechecked == [assessment_id]
    assert result.anonymized_assessment_ids == []
    assert snapshot(seeded_session) == anonymized_snapshots[0]
    assessment = seeded_session.get(Assessment, assessment_id)
    assert assessment is not None and assessment.anonymized_at == now
    assert assessment.responses_json == {"anonymized": True}
    events = list(
        seeded_session.scalars(
            select(AuditEvent).where(
                AuditEvent.entity_id == assessment_id,
                AuditEvent.event_type == "candidate_data.anonymized",
            )
        )
    )
    assert len(events) == 1
    before = snapshot(seeded_session)
    assert service.run_retention(now=now).anonymized_assessment_ids == []
    assert snapshot(seeded_session) == before
