"""Local queue transactions and isolated PostgreSQL concurrency evidence."""

from __future__ import annotations

import base64
import os
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier, local
from typing import Any
from uuid import UUID, uuid4

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import Engine, MetaData, create_engine, event, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema

from app.auth.config import AuthenticationSettings
from app.auth.context import AuthorizationContext, OrganizationScope
from app.auth.errors import AccessProblemError
from app.database.base import Base
from app.database.models import (
    AssessmentInvite,
    AssessmentInviteStatus,
    AuditEvent,
    InternalUserRole,
    InvitationDelivery,
    Role,
    User,
)
from app.database.seed import (
    ALPHA_ORGANIZATION_ID,
    ALPHA_PROFILE_ID,
    ALPHA_ROLE_ID,
    ALPHA_USER_ID,
    BEACON_ORGANIZATION_ID,
    seed_database,
)
from app.database.session import REQUEST_TRANSACTION_INFO_KEY, create_session_factory
from app.invitations.config import InvitationSettings
from app.invitations.delivery import InvitationDeliveryError, InvitationEmail
from app.invitations.local_delivery import LocalSmtpInvitationDelivery
from app.invitations.queue import local_cipher, replay_invitation
from app.invitations.recovery import DeliveryEvent, DeliveryState
from app.invitations.schemas import InvitationCreateRequest
from app.invitations.service import InternalInvitationService
from app.invitations.tokens import InviteTokenCodec
from app.invitations.worker import LocalDeliveryWorker, cleanup_deliveries
from app.main import create_app
from tests.test_auth_tokens import AUDIENCE, ISSUER, SECRET
from tests.test_database_migrations import alembic_config
from tests.test_invitations import INVITE_SECRET, auth_header

KEY = "synthetic-delivery-request-0001"


def settings(**overrides: Any) -> InvitationSettings:
    return InvitationSettings(
        _env_file=None,
        **{
            "local_queue_enabled": True,
            "allow_synthetic_definitions": True,
            "local_queue_key": base64.urlsafe_b64encode(b"q" * 32).decode(),
            "token_signing_secret": INVITE_SECRET,
            "candidate_base_url": "http://127.0.0.1:3146/candidate/invites",
            **overrides,
        },
    )


def authentication(**overrides: Any) -> AuthenticationSettings:
    return AuthenticationSettings(
        _env_file=None,
        **{
            "environment": "development",
            "jwt_secret": SECRET,
            "jwt_issuer": ISSUER,
            "jwt_audience": AUDIENCE,
            **overrides,
        },
    )


def service(
    session: Session, *, organization_id: UUID = ALPHA_ORGANIZATION_ID
) -> InternalInvitationService:
    policy = settings()
    context = AuthorizationContext(
        user_id=ALPHA_USER_ID,
        organization=OrganizationScope(organization_id),
        email="recruiter@example.test",
        name="Synthetic recruiter",
        role=InternalUserRole.RECRUITER,
    )
    return InternalInvitationService(
        session,
        context,
        policy,
        InviteTokenCodec(INVITE_SECRET),
        LocalSmtpInvitationDelivery(enabled=True),
        queue_cipher=local_cipher(policy, authentication()),
    )


def issue(
    session: Session, *, key: str = KEY, email: str = "candidate@example.test"
) -> AssessmentInvite:
    return service(session).create(
        ALPHA_ROLE_ID,
        InvitationCreateRequest(
            role_profile_id=ALPHA_PROFILE_ID,
            email=email,
        ),
        idempotency_key=key,
    )


@pytest.fixture(params=["postgresql"])
def queue_factory(
    request: pytest.FixtureRequest, database_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> Generator[sessionmaker[Session]]:
    engine = database_engine
    admin = None
    schema = f"delivery_{uuid4().hex}"
    if request.param == "postgresql":
        raw = os.environ.get("TEST_DELIVERY_POSTGRES_URL")
        if not raw:
            pytest.skip("Set isolated TEST_DELIVERY_POSTGRES_URL for PostgreSQL evidence")
        url = make_url(raw)
        assert (
            url.host == "127.0.0.1"
            and (url.port, url.database)
            in {(5586, "iopsych_delivery"), (5606, "iopsych_reconcile")}
            and not url.query
        )
        admin = create_engine(url)
        with admin.begin() as connection:
            connection.execute(CreateSchema(schema))
        url = url.update_query_dict(
            {"options": f"-csearch_path={schema} -cstatement_timeout=10000"}
        )
        rendered = url.render_as_string(hide_password=False)
        monkeypatch.setenv("DATABASE_URL", rendered)
        command.upgrade(alembic_config(rendered), "20261104_0008")
        engine = create_engine(url)
    with Session(database_engine) as session:
        seed_database(session)
        session.commit()
    historical = MetaData()
    historical.reflect(bind=engine)
    with database_engine.connect() as source, engine.begin() as target:
        for table in Base.metadata.sorted_tables:
            rows = source.execute(select(table)).mappings().all()
            if rows:
                old_table = historical.tables[table.name]
                target.execute(
                    old_table.insert(),
                    [{column.name: row[column.name] for column in old_table.c} for row in rows],
                )
    factory = create_session_factory(engine)
    with factory() as session:
        roles_before = session.scalar(select(func.count()).select_from(Role))
    if admin is not None:
        command.upgrade(alembic_config(rendered), "head")
        with factory() as session:
            assert session.scalar(select(func.count()).select_from(Role)) == roles_before
    with factory() as session:
        user = session.get(User, ALPHA_USER_ID)
        assert user is not None
        assert user.is_active is True and user.version == 1
        user.auth_subject = "provider-alpha-recruiter"
        session.commit()
    try:
        yield factory
    finally:
        if admin is not None:
            engine.dispose()
            with admin.begin() as connection:
                connection.execute(DropSchema(schema, cascade=True))
            admin.dispose()


@pytest.fixture
def captured(monkeypatch: pytest.MonkeyPatch) -> list[InvitationEmail]:
    messages: list[InvitationEmail] = []
    monkeypatch.setattr(
        LocalSmtpInvitationDelivery, "send", lambda self, message: messages.append(message)
    )
    return messages


def worker(factory: sessionmaker[Session]) -> LocalDeliveryWorker:
    return LocalDeliveryWorker(
        factory, settings(), authentication(), LocalSmtpInvitationDelivery(enabled=True)
    )


def test_queue_commits_before_send_and_replays_without_new_assignment(
    queue_factory: sessionmaker[Session],
    captured: list[InvitationEmail],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with queue_factory() as session:
        invite = issue(session)
        identifier = invite.id
        assert invite.status is AssessmentInviteStatus.PENDING_DELIVERY
        assert captured == []
        job = session.scalar(select(InvitationDelivery))
        assert job is not None and job.credential_ciphertext
        assert b"http" not in job.credential_ciphertext
    with monkeypatch.context() as patcher:
        patcher.setattr(
            "app.invitations.service.new_assignment",
            lambda **kwargs: pytest.fail("replay assigned"),
        )
        with queue_factory() as session:
            assert issue(session).id == identifier
    assert worker(queue_factory).drain() == 1
    assert len(captured) == 1
    token = captured[0].text_body.split("/candidate/invites/")[1].split()[0]
    with queue_factory() as session:
        loaded_invite = session.get(AssessmentInvite, identifier)
        job = session.scalar(select(InvitationDelivery))
        assert loaded_invite is not None and job is not None
        assert loaded_invite.status is AssessmentInviteStatus.ACTIVE
        assert InviteTokenCodec(INVITE_SECRET).validate_and_hash(token) == loaded_invite.token_hash
        assert job.state is DeliveryState.SENT and job.attempt_count == 1
        assert job.credential_ciphertext is None and job.credential_key_id is None
        assert token not in str(session.scalars(select(AuditEvent.metadata_json)).all())
        assert issue(session).id == identifier
    assert worker(queue_factory).drain() == 0


def test_conflict_and_cross_tenant_replay(queue_factory: sessionmaker[Session]) -> None:
    with queue_factory() as session:
        issue(session)
        with pytest.raises(AccessProblemError) as changed:
            issue(session, email="changed@example.test")
        assert changed.value.code == "idempotency_conflict"
        with pytest.raises(AccessProblemError) as foreign:
            service(session, organization_id=BEACON_ORGANIZATION_ID).create(
                ALPHA_ROLE_ID,
                InvitationCreateRequest(
                    role_profile_id=ALPHA_PROFILE_ID, email="candidate@example.test"
                ),
                idempotency_key=KEY,
            )
        assert foreign.value.status == 404
        assert session.scalar(select(func.count()).select_from(InvitationDelivery)) == 1


@pytest.mark.parametrize("phase", ["sending", "sent"])
def test_claim_or_completion_audit_failure_never_resends(
    queue_factory: sessionmaker[Session], captured: list[InvitationEmail], phase: str
) -> None:
    with queue_factory() as session:
        issue(session)

    def fail_commit(session: Session) -> None:
        if any(
            isinstance(row, InvitationDelivery) and row.state.value == phase
            for row in session.identity_map.values()
        ):
            raise SQLAlchemyError("synthetic transaction failure")

    event.listen(queue_factory, "before_commit", fail_commit)
    try:
        with pytest.raises(SQLAlchemyError):
            worker(queue_factory).drain()
    finally:
        event.remove(queue_factory, "before_commit", fail_commit)
    with queue_factory() as session:
        job = session.scalar(select(InvitationDelivery))
        assert job is not None
        assert job.state is (DeliveryState.QUEUED if phase == "sending" else DeliveryState.SENDING)
        assert len(captured) == (0 if phase == "sending" else 1)
    if phase == "sent":
        assert cleanup_deliveries(queue_factory, now=datetime.now(UTC) + timedelta(minutes=3)) == 1
        assert worker(queue_factory).drain() == 0
        with queue_factory() as session:
            job = session.scalar(select(InvitationDelivery))
            assert job is not None and job.state is DeliveryState.UNCERTAIN
            assert job.credential_ciphertext is None
    else:
        assert worker(queue_factory).drain() == 1


def test_timeout_requires_revoke_reissue(
    queue_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[int] = []

    def accepted_then_timeout(self: LocalSmtpInvitationDelivery, message: InvitationEmail) -> None:
        calls.append(1)
        raise InvitationDeliveryError("synthetic timeout")

    monkeypatch.setattr(LocalSmtpInvitationDelivery, "send", accepted_then_timeout)
    with queue_factory() as session:
        identifier = issue(session).id
    assert worker(queue_factory).drain() == 1
    assert worker(queue_factory).drain() == 0
    assert calls == [1]
    with queue_factory() as session:
        job = session.scalar(select(InvitationDelivery))
        assert job is not None and job.state is DeliveryState.UNCERTAIN
        assert job.credential_ciphertext is None
        with pytest.raises(AccessProblemError) as error:
            issue(session)
        assert error.value.code == "invitation_reissue_required"
        with pytest.raises(AccessProblemError):
            issue(session, key=KEY + "-must-revoke-first")
        service(session).revoke(ALPHA_ROLE_ID, identifier)
        assert issue(session, key=KEY + "-replacement").id != identifier


def test_revoke_during_send_cannot_activate(
    queue_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    with queue_factory() as session:
        identifier = issue(session).id

    def revoke_during_send(self: LocalSmtpInvitationDelivery, message: InvitationEmail) -> None:
        with queue_factory() as session:
            service(session).revoke(ALPHA_ROLE_ID, identifier)

    monkeypatch.setattr(LocalSmtpInvitationDelivery, "send", revoke_during_send)
    assert worker(queue_factory).drain() == 1
    with queue_factory() as session:
        loaded_invite = session.get(AssessmentInvite, identifier)
        job = session.scalar(select(InvitationDelivery))
        assert loaded_invite is not None and loaded_invite.status is AssessmentInviteStatus.REVOKED
        assert job is not None and job.state is DeliveryState.CANCELLED
        assert job.credential_ciphertext is None


def test_cleanup_is_bounded_and_keyless(queue_factory: sessionmaker[Session]) -> None:
    with queue_factory() as session:
        issue(session)
        issue(session, key=KEY + "-second")
    future = datetime.now(UTC) + timedelta(minutes=16)
    assert cleanup_deliveries(queue_factory, limit=1, now=future) == 1
    with queue_factory() as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(InvitationDelivery)
                .where(InvitationDelivery.credential_ciphertext.is_not(None))
            )
            == 1
        )
    assert cleanup_deliveries(queue_factory, limit=1, now=future) == 1
    assert worker(queue_factory).drain() == 0


def test_api_audit_failure_rolls_back_queue(
    queue_factory: sessionmaker[Session], captured: list[InvitationEmail]
) -> None:
    app = create_app(
        authentication_settings=authentication(),
        invitation_settings=settings(),
        session_factory=queue_factory,
    )

    def fail_audit(session: Session) -> None:
        if not session.in_nested_transaction() and any(
            isinstance(row, AuditEvent) and row.event_type == "assessment_invite.created"
            for row in session.new
        ):
            raise SQLAlchemyError("synthetic audit failure")

    event.listen(queue_factory, "before_commit", fail_audit)
    try:
        with TestClient(app) as client:
            response = client.post(
                f"/v1/roles/{ALPHA_ROLE_ID}/invites",
                json={
                    "role_profile_id": str(ALPHA_PROFILE_ID),
                    "email": "candidate@example.test",
                },
                headers={
                    **auth_header("provider-alpha-recruiter", ALPHA_ORGANIZATION_ID),
                    "Idempotency-Key": KEY,
                },
            )
        assert response.status_code == 500
        assert response.json()["code"] == "audit_persistence_failed"
    finally:
        event.remove(queue_factory, "before_commit", fail_audit)
    with queue_factory() as session:
        assert session.scalar(select(func.count()).select_from(InvitationDelivery)) == 0
        assert session.scalar(select(func.count()).select_from(AssessmentInvite)) == 0
    assert captured == []


def test_postgres_concurrent_duplicate_preserves_outer_work(
    queue_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    with queue_factory() as session:
        if session.get_bind().dialect.name != "postgresql":
            pytest.skip("Real PostgreSQL locking/concurrency evidence")
    from app.invitations import service as service_module

    original = replay_invitation
    barrier = Barrier(2)
    state = local()

    def synchronized_replay(*args: Any, **kwargs: Any) -> AssessmentInvite | None:
        result = original(*args, **kwargs)
        if not getattr(state, "checked", False):
            state.checked = True
            barrier.wait(timeout=5)
        return result

    monkeypatch.setattr(service_module, "replay_invitation", synchronized_replay)

    def issue_in_request() -> UUID:
        with queue_factory() as session:
            session.info[REQUEST_TRANSACTION_INFO_KEY] = True
            session.add(
                AuditEvent(
                    organization_id=ALPHA_ORGANIZATION_ID,
                    actor_id=ALPHA_USER_ID,
                    event_type="synthetic.outer_work",
                    entity_type="role",
                    entity_id=ALPHA_ROLE_ID,
                    metadata_json={},
                )
            )
            identifier = issue(session).id
            session.commit()
            return identifier

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: issue_in_request(), range(2)))
    assert results[0] == results[1]
    with queue_factory() as session:
        assert session.scalar(select(func.count()).select_from(InvitationDelivery)) == 1
        assert session.scalar(select(func.count()).select_from(AssessmentInvite)) == 1
        assert (
            session.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.event_type == "synthetic.outer_work")
            )
            == 2
        )


@pytest.mark.parametrize(
    "override",
    [
        {"local_queue_enabled": False},
        {"local_queue_key": None},
        {"allow_synthetic_definitions": False},
        {"candidate_base_url": "https://example.invalid/invites"},
        {
            "local_queue_key": base64.urlsafe_b64encode(SECRET.encode()[:32]).decode(),
            "token_signing_secret": SECRET[:32],
        },
    ],
)
def test_configuration_fails_closed(override: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        local_cipher(settings(**override), authentication())


def test_production_mode_cannot_enable_local_queue() -> None:
    with pytest.raises(ValueError):
        local_cipher(settings(), authentication(environment="production"))


def test_non_postgres_queue_fails_closed(database_engine: Engine) -> None:
    factory = create_session_factory(database_engine)
    with factory() as session:
        seed_database(session)
        session.commit()
        with pytest.raises(AccessProblemError) as error:
            issue(session)
        assert error.value.code == "local_queue_requires_postgresql"
    with pytest.raises(AccessProblemError):
        worker(factory)
    with pytest.raises(AccessProblemError):
        cleanup_deliveries(factory)


@pytest.mark.parametrize("key", [None, "short", "x" * 129, "invalid key with spaces"])
def test_invalid_idempotency_header_never_queues(
    queue_factory: sessionmaker[Session], key: str | None
) -> None:
    with queue_factory() as session:
        with pytest.raises(AccessProblemError) as error:
            service(session).create(
                ALPHA_ROLE_ID,
                InvitationCreateRequest(
                    role_profile_id=ALPHA_PROFILE_ID,
                    email="candidate@example.test",
                ),
                idempotency_key=key,
            )
        assert error.value.code == "invalid_idempotency_key"
        assert session.scalar(select(func.count()).select_from(InvitationDelivery)) == 0


def test_real_recipient_rejected_before_credential_storage(
    queue_factory: sessionmaker[Session],
) -> None:
    with queue_factory() as session:
        with pytest.raises(AccessProblemError) as error:
            issue(session, email="candidate@example.com")
        assert error.value.code == "synthetic_recipient_required"
        assert session.scalar(select(func.count()).select_from(InvitationDelivery)) == 0


def test_api_pending_response_compatible_and_replayed(
    queue_factory: sessionmaker[Session], captured: list[InvitationEmail]
) -> None:
    app = create_app(
        authentication_settings=authentication(),
        invitation_settings=settings(),
        session_factory=queue_factory,
    )
    with TestClient(app) as client:
        headers = {
            **auth_header("provider-alpha-recruiter", ALPHA_ORGANIZATION_ID),
            "Idempotency-Key": KEY,
        }
        path = f"/v1/roles/{ALPHA_ROLE_ID}/invites"
        payload = {"role_profile_id": str(ALPHA_PROFILE_ID), "email": "candidate@example.test"}
        first = client.post(path, json=payload, headers=headers)
        second = client.post(path, json=payload, headers=headers)
    assert first.status_code == second.status_code == 201
    assert first.json() == second.json()
    assert first.json()["status"] == "pending_delivery"
    assert set(first.json()) == {
        "id",
        "role_profile_id",
        "email",
        "expires_at",
        "status",
        "sent_at",
        "revoked_at",
        "created_at",
        "delivery_state",
    }
    assert captured == []


def test_bad_local_config_returns_safe_problem(queue_factory: sessionmaker[Session]) -> None:
    app = create_app(
        authentication_settings=authentication(environment="production"),
        invitation_settings=settings(),
        session_factory=queue_factory,
    )
    with TestClient(app) as client:
        response = client.post(
            f"/v1/roles/{ALPHA_ROLE_ID}/invites",
            json={
                "role_profile_id": str(ALPHA_PROFILE_ID),
                "email": "candidate@example.test",
            },
            headers={
                **auth_header("provider-alpha-recruiter", ALPHA_ORGANIZATION_ID),
                "Idempotency-Key": KEY,
            },
        )
    assert response.status_code == 503
    assert response.json()["code"] == "invitation_service_unavailable"


def test_wrong_key_or_tampered_ciphertext_never_sends(
    queue_factory: sessionmaker[Session], captured: list[InvitationEmail]
) -> None:
    with queue_factory() as session:
        issue(session)
        job = session.scalar(select(InvitationDelivery))
        assert job is not None and job.credential_ciphertext is not None
        job.credential_ciphertext = job.credential_ciphertext[:-1] + bytes(
            [job.credential_ciphertext[-1] ^ 1]
        )
        session.commit()
    assert worker(queue_factory).drain() == 1
    assert captured == []
    with queue_factory() as session:
        job = session.scalar(select(InvitationDelivery))
        assert job is not None and job.state is DeliveryState.UNCERTAIN
        assert job.credential_ciphertext is None


def test_cross_tenant_corrupt_job_cannot_send(
    queue_factory: sessionmaker[Session], captured: list[InvitationEmail]
) -> None:
    with queue_factory() as session:
        issue(session)
        job = session.scalar(select(InvitationDelivery))
        assert job is not None
        job.organization_id = BEACON_ORGANIZATION_ID
        session.commit()
    assert worker(queue_factory).drain() == 0
    assert captured == []
    with queue_factory() as session:
        job = session.scalar(select(InvitationDelivery))
        assert job is not None and job.state is DeliveryState.CANCELLED
        assert job.credential_ciphertext is None
        assert (
            session.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(
                    AuditEvent.organization_id == BEACON_ORGANIZATION_ID,
                    AuditEvent.event_type.like("invitation_delivery.%"),
                )
            )
            == 0
        )


def test_concurrent_workers_send_one_committed_claim(
    queue_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    from threading import Event

    with queue_factory() as session:
        identifier = issue(session).id
    accepted = Event()
    release = Event()
    calls: list[int] = []

    def blocked_send(self: LocalSmtpInvitationDelivery, message: InvitationEmail) -> None:
        calls.append(1)
        with queue_factory() as observer:
            job = observer.scalar(select(InvitationDelivery))
            assert job is not None and job.state is DeliveryState.SENDING
        accepted.set()
        assert release.wait(timeout=5)

    monkeypatch.setattr(LocalSmtpInvitationDelivery, "send", blocked_send)
    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(worker(queue_factory).drain)
        assert accepted.wait(timeout=5)
        try:
            assert executor.submit(worker(queue_factory).drain).result(timeout=5) == 0
        finally:
            release.set()
        assert first.result(timeout=5) == 1
    assert calls == [1]
    with queue_factory() as session:
        invite = session.get(AssessmentInvite, identifier)
        assert invite is not None and invite.status is AssessmentInviteStatus.ACTIVE


def test_pending_credentials_block_migration_downgrade(
    queue_factory: sessionmaker[Session],
) -> None:
    with queue_factory() as session:
        identifier = issue(session).id
        url = session.get_bind().engine.url.render_as_string(hide_password=False)
    # Exercise the retained queue migration guard directly: the newer notice
    # migration also correctly blocks a full downgrade once notice evidence exists.
    import runpy
    from pathlib import Path

    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    migration = runpy.run_path(
        str(Path(__file__).parents[1] / "alembic/versions/20261104_0009_invitation_deliveries.py")
    )
    with queue_factory() as probe:
        engine = probe.get_bind()
        assert isinstance(engine, Engine)
    with (
        engine.begin() as connection,
        Operations.context(MigrationContext.configure(connection)),
        pytest.raises(RuntimeError, match="Cancel or expire"),
    ):
        migration["downgrade"]()
    with pytest.raises(RuntimeError, match="notice evidence"):
        command.downgrade(alembic_config(url), "20261104_0008")
    with queue_factory() as session:
        service(session).revoke(ALPHA_ROLE_ID, identifier)
    with pytest.raises(RuntimeError, match="notice evidence"):
        command.downgrade(alembic_config(url), "20261104_0008")


def test_invalid_worker_batch_and_adapter(queue_factory: sessionmaker[Session]) -> None:
    for limit in (0, 101, True):
        with pytest.raises(ValueError):
            worker(queue_factory).drain(limit=limit)
    with pytest.raises(ValueError, match="local SMTP"):
        LocalDeliveryWorker(queue_factory, settings(), authentication(), object())  # type: ignore[arg-type]


def test_privacy_erasure_clears_queued_credentials_atomically(
    queue_factory: sessionmaker[Session],
) -> None:
    from app.database.models import Assessment
    from app.invitations.queue import stage_delivery
    from app.privacy.config import PrivacySettings
    from app.privacy.service import PrivacyService
    from tests.test_privacy import candidate_record

    assessment_id, token = candidate_record(queue_factory)
    with queue_factory() as session:
        assessment = session.get(Assessment, assessment_id)
        assert assessment is not None
        invite = session.get(AssessmentInvite, assessment.invite_id)
        assert invite is not None
        stage_delivery(
            session,
            invite=invite,
            organization_id=ALPHA_ORGANIZATION_ID,
            actor_id=ALPHA_USER_ID,
            digests=("f" * 64, "e" * 64),
            raw_token=token,
            cipher=local_cipher(settings(), authentication()),
            key_id="local-v1",
        )
        session.commit()
        admin = AuthorizationContext(
            user_id=ALPHA_USER_ID,
            organization=OrganizationScope(ALPHA_ORGANIZATION_ID),
            email="admin@example.test",
            name="Synthetic admin",
            role=InternalUserRole.ADMIN,
        )
        PrivacyService(session, PrivacySettings(), admin).anonymize(assessment_id)
        job = session.scalar(select(InvitationDelivery))
        assert job is not None and job.state is DeliveryState.CANCELLED
        assert job.credential_ciphertext is None and job.credential_key_id is None
        assert invite.status is AssessmentInviteStatus.REVOKED


def test_stage_rejects_tenant_mismatch(queue_factory: sessionmaker[Session]) -> None:
    from app.invitations.queue import stage_delivery

    with queue_factory() as session:
        invite = issue(session)
        with pytest.raises(ValueError, match="tenant mismatch"):
            stage_delivery(
                session,
                invite=invite,
                organization_id=BEACON_ORGANIZATION_ID,
                actor_id=ALPHA_USER_ID,
                digests=("f" * 64, "e" * 64),
                raw_token="never encrypted",
                cipher=local_cipher(settings(), authentication()),
                key_id="local-v1",
            )


def test_lost_key_does_not_block_api_revocation(queue_factory: sessionmaker[Session]) -> None:
    with queue_factory() as session:
        identifier = issue(session).id
    app = create_app(
        authentication_settings=authentication(),
        invitation_settings=settings(local_queue_key=None),
        session_factory=queue_factory,
    )
    with TestClient(app) as client:
        response = client.post(
            f"/v1/roles/{ALPHA_ROLE_ID}/invites/{identifier}/revoke",
            headers=auth_header("provider-alpha-recruiter", ALPHA_ORGANIZATION_ID),
        )
    assert response.status_code == 200
    assert response.json()["status"] == "revoked"
    with queue_factory() as session:
        job = session.scalar(select(InvitationDelivery))
        assert job is not None and job.state is DeliveryState.CANCELLED
        assert job.credential_ciphertext is None


def test_worker_drain_respects_claim_limit(
    queue_factory: sessionmaker[Session], captured: list[InvitationEmail]
) -> None:
    with queue_factory() as session:
        for index in range(3):
            issue(session, key=f"{KEY}-{index}")
    assert worker(queue_factory).drain(limit=2) == 2
    assert len(captured) == 2
    with queue_factory() as session:
        jobs = session.scalars(select(InvitationDelivery)).all()
        assert sum(job.state is DeliveryState.SENT for job in jobs) == 2
        assert sum(job.state is DeliveryState.QUEUED for job in jobs) == 1
        assert sum(job.attempt_count for job in jobs) == 2
    assert worker(queue_factory).drain(limit=2) == 1
    assert len(captured) == 3


def test_recovery_during_send_cannot_reactivate_or_retry(
    queue_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    with queue_factory() as session:
        identifier = issue(session).id
    calls: list[int] = []

    def recover_during_send(self: LocalSmtpInvitationDelivery, message: InvitationEmail) -> None:
        calls.append(1)
        assert cleanup_deliveries(queue_factory, now=datetime.now(UTC) + timedelta(minutes=3)) == 1

    monkeypatch.setattr(LocalSmtpInvitationDelivery, "send", recover_during_send)
    assert worker(queue_factory).drain() == 1
    assert worker(queue_factory).drain() == 0
    assert calls == [1]
    with queue_factory() as session:
        invite = session.get(AssessmentInvite, identifier)
        job = session.scalar(select(InvitationDelivery))
        assert invite is not None and invite.status is AssessmentInviteStatus.PENDING_DELIVERY
        assert invite.sent_at is None
        assert job is not None and job.state is DeliveryState.UNCERTAIN
        assert job.attempt_count == 1
        assert job.credential_ciphertext is None and job.credential_key_id is None


@pytest.mark.parametrize("mutation", ["key", "expiry", "swap"])
def test_changed_credential_binding_never_sends(
    queue_factory: sessionmaker[Session], captured: list[InvitationEmail], mutation: str
) -> None:
    with queue_factory() as session:
        issue(session)
        job = session.scalar(select(InvitationDelivery))
        assert job is not None
        if mutation == "key":
            job.credential_key_id = "unavailable-key"
        elif mutation == "expiry":
            job.credential_expires_at += timedelta(seconds=1)
        else:
            second = issue(session, key=KEY + "-second")
            other = session.scalar(
                select(InvitationDelivery).where(InvitationDelivery.invite_id == second.id)
            )
            assert other is not None
            job.credential_ciphertext, other.credential_ciphertext = (
                other.credential_ciphertext,
                job.credential_ciphertext,
            )
        session.commit()
    count = 2 if mutation == "swap" else 1
    assert worker(queue_factory).drain() == count
    assert worker(queue_factory).drain() == 0
    assert captured == []
    with queue_factory() as session:
        jobs = session.scalars(select(InvitationDelivery)).all()
        assert len(jobs) == count
        for job in jobs:
            assert job.state is DeliveryState.UNCERTAIN and job.attempt_count == 1
            assert job.credential_ciphertext is None and job.credential_key_id is None


def test_cleanup_skips_locked_invite_then_recovers(
    queue_factory: sessionmaker[Session], captured: list[InvitationEmail]
) -> None:
    with queue_factory() as session:
        identifier = issue(session).id
    future = datetime.now(UTC) + timedelta(minutes=16)
    with queue_factory() as locked, locked.begin():
        locked.scalar(
            select(AssessmentInvite).where(AssessmentInvite.id == identifier).with_for_update()
        )
        with ThreadPoolExecutor(max_workers=1) as executor:
            assert (
                executor.submit(cleanup_deliveries, queue_factory, now=future).result(timeout=5)
                == 0
            )
    assert cleanup_deliveries(queue_factory, now=future) == 1
    assert worker(queue_factory).drain() == 0
    assert captured == []
    with queue_factory() as session:
        job = session.scalar(select(InvitationDelivery))
        assert job is not None and job.state is DeliveryState.EXPIRED
        assert job.attempt_count == 0
        assert job.credential_ciphertext is None and job.credential_key_id is None


@pytest.mark.parametrize("missing", ["invite", "job", "claim"])
def test_completion_rejects_disappeared_or_replaced_claim(
    queue_factory: sessionmaker[Session], captured: list[InvitationEmail], missing: str
) -> None:
    from dataclasses import replace

    with queue_factory() as session:
        identifier = issue(session).id
    delivery_worker = worker(queue_factory)
    claim = delivery_worker._claim()
    assert claim is not None
    with queue_factory() as session:
        job = session.scalar(select(InvitationDelivery))
        assert job is not None and job.state is DeliveryState.SENDING
        if missing == "claim":
            claim = replace(claim, delivery_id=uuid4())
        else:
            session.delete(job)
            session.flush()
            if missing == "invite":
                invite = session.get(AssessmentInvite, identifier)
                assert invite is not None
                session.delete(invite)
        session.commit()
    with pytest.raises(ValueError, match=r"delivery .* is unavailable"):
        delivery_worker._complete(claim, DeliveryEvent.ACCEPTED)
    assert delivery_worker.drain() == 0
    assert captured == []
    with queue_factory() as session:
        invite = session.get(AssessmentInvite, identifier)
        if missing == "invite":
            assert invite is None
        else:
            assert invite is not None and invite.status is AssessmentInviteStatus.PENDING_DELIVERY
            assert invite.sent_at is None


def test_replay_rejects_broken_role_binding(queue_factory: sessionmaker[Session]) -> None:
    with queue_factory() as session:
        issue(session)
        job = session.scalar(select(InvitationDelivery))
        assert job is not None
        with pytest.raises(AccessProblemError) as error:
            replay_invitation(
                session,
                ALPHA_ORGANIZATION_ID,
                uuid4(),
                (job.idempotency_digest, job.request_digest),
            )
        assert error.value.code == "delivery_integrity_failed"


def test_cancel_without_delivery_is_safe(queue_factory: sessionmaker[Session]) -> None:
    from app.invitations.queue import cancel_delivery

    with queue_factory() as session:
        cancel_delivery(session, uuid4())
        session.commit()
        assert session.scalar(select(func.count()).select_from(InvitationDelivery)) == 0


def test_audit_rejects_unresolvable_owner(queue_factory: sessionmaker[Session]) -> None:
    from app.invitations.worker import _audit

    with queue_factory() as session:
        before = session.scalar(select(func.count()).select_from(AuditEvent))
        orphan = InvitationDelivery(
            invite_id=uuid4(), organization_id=BEACON_ORGANIZATION_ID, state=DeliveryState.UNCERTAIN
        )
        with pytest.raises(ValueError, match="delivery audit owner is unavailable"):
            _audit(session, orphan)
        session.commit()
        assert session.scalar(select(func.count()).select_from(AuditEvent)) == before


@pytest.mark.parametrize("disappeared", [True, False])
def test_cleanup_rechecks_selected_delivery(
    queue_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch, disappeared: bool
) -> None:
    from app.invitations import worker as worker_module

    with queue_factory() as session:
        identifier = issue(session).id
        audit_count = session.scalar(select(func.count()).select_from(AuditEvent))
    locked_job = worker_module._locked_job
    inspected: list[UUID] = []

    def changed_job(session: Session, invite_id: UUID) -> InvitationDelivery | None:
        inspected.append(invite_id)
        job = locked_job(session, invite_id)
        assert job is not None
        if disappeared:
            session.delete(job)
            session.flush()
            return None
        job.state = DeliveryState.CANCELLED
        job.credential_ciphertext = None
        job.credential_key_id = None
        session.flush()
        return job

    monkeypatch.setattr(worker_module, "_locked_job", changed_job)
    assert cleanup_deliveries(queue_factory, now=datetime.now(UTC) + timedelta(minutes=16)) == 0
    assert inspected == [identifier]
    with queue_factory() as session:
        assert session.scalar(select(func.count()).select_from(AuditEvent)) == audit_count
        invite = session.get(AssessmentInvite, identifier)
        assert invite is not None and invite.status is AssessmentInviteStatus.PENDING_DELIVERY
        assert invite.sent_at is None
        job = session.scalar(select(InvitationDelivery))
        if disappeared:
            assert job is None
        else:
            assert job is not None and job.state is DeliveryState.CANCELLED
            assert job.attempt_count == 0
            assert job.credential_ciphertext is None and job.credential_key_id is None
