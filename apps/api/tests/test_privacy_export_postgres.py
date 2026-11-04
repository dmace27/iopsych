"""Real PostgreSQL export/erasure serialization using disposable synthetic schemas."""

import os
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from queue import Queue
from time import monotonic, sleep
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema

from alembic import command
from app.auth.config import AuthenticationSettings
from app.auth.context import AuthorizationContext, OrganizationScope
from app.auth.errors import AccessProblemError
from app.database.models import Assessment, AuditEvent, InternalUserRole, User
from app.database.seed import ALPHA_ORGANIZATION_ID, ALPHA_USER_ID, seed_database
from app.database.session import REQUEST_TRANSACTION_INFO_KEY, create_session_factory
from app.invitations.config import InvitationSettings
from app.main import create_app
from app.privacy.config import PrivacySettings
from app.privacy.service import PrivacyService, _CandidateRecord
from tests.test_auth_tokens import AUDIENCE, ISSUER, SECRET
from tests.test_database_migrations import alembic_config
from tests.test_privacy import ADMIN_SUBJECT, candidate_record, headers


@pytest.fixture
def export_factory(monkeypatch: pytest.MonkeyPatch) -> Generator[sessionmaker[Session]]:
    database_url = os.environ.get("TEST_POSTGRES_URL", "")
    if not database_url or make_url(database_url).get_backend_name() != "postgresql":
        pytest.skip("Export concurrency requires an explicit isolated TEST_POSTGRES_URL")
    schema = f"privacy_export_{uuid4().hex}"
    admin_engine = create_engine(database_url)
    with admin_engine.begin() as connection:
        connection.execute(CreateSchema(schema))
    url = make_url(database_url).update_query_dict(
        {"options": f"-csearch_path={schema} -cstatement_timeout=10000"}
    )
    isolated_url = url.render_as_string(hide_password=False)
    engine = create_engine(url)
    try:
        monkeypatch.setenv("DATABASE_URL", isolated_url)
        command.upgrade(alembic_config(isolated_url), "head")
        factory = create_session_factory(engine)
        with factory() as session:
            seed_database(session)
            admin = session.get(User, ALPHA_USER_ID)
            assert admin is not None
            admin.auth_subject = ADMIN_SUBJECT
            admin.role = InternalUserRole.ADMIN
            session.commit()
        yield factory
    finally:
        engine.dispose()
        with admin_engine.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        admin_engine.dispose()


def service(session: Session) -> PrivacyService:
    return PrivacyService(
        session,
        PrivacySettings(),
        AuthorizationContext(
            user_id=ALPHA_USER_ID,
            organization=OrganizationScope(ALPHA_ORGANIZATION_ID),
            email="synthetic-admin@example.invalid",
            name="Synthetic admin",
            role=InternalUserRole.ADMIN,
        ),
    )


def assert_blocked(holder: Session, waiter_pid: int) -> None:
    holder_pid = holder.scalar(text("SELECT pg_backend_pid()"))
    deadline = monotonic() + 5
    while monotonic() < deadline:
        blockers = holder.scalar(text("SELECT pg_blocking_pids(:pid)"), {"pid": waiter_pid})
        if holder_pid in blockers:
            return
        sleep(0.01)
    pytest.fail("Second PostgreSQL connection did not wait on the assessment lock")


def test_export_first_materializes_before_erasure_and_commit(
    export_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    assessment_id, _ = candidate_record(
        export_factory, submitted_at=datetime.now(UTC), with_report=True
    )
    pid: Queue[int] = Queue()

    def erase() -> None:
        with export_factory() as session:
            pid.put(session.scalar(text("SELECT pg_backend_pid()")))
            service(session).anonymize(assessment_id)

    with export_factory() as holder, ThreadPoolExecutor(max_workers=1) as executor:
        exporter = service(holder)
        original_get_record = exporter._get_record
        pending = []

        def get_record(identifier: UUID, *, lock: bool = False) -> _CandidateRecord:
            record = original_get_record(identifier, lock=lock)
            pending.append(executor.submit(erase))
            assert_blocked(holder, pid.get(timeout=5))
            return record

        monkeypatch.setattr(exporter, "_get_record", get_record)
        try:
            envelope = exporter.export(assessment_id)
            assert not pending[0].done()
            snapshot = envelope.model_dump(mode="json")
            assert snapshot["schema_version"] == "1.0"
            assert snapshot["invitation"]["email"].startswith("candidate-")
            assert snapshot["invitation"]["status"] == "consented"
            assert snapshot["assessment"]["definition"] == {"definition": "retained"}
            assert snapshot["assessment"]["responses"] == {"responses": ["retained"]}
            assert snapshot["assessment"]["scores"] == {"scores": ["retained"]}
            assert snapshot["reports"][0]["result"] == {"derived": "candidate data"}
            assert [item["event_type"] for item in snapshot["activity"]] == ["assessment.submitted"]
            holder.add(
                AuditEvent(
                    organization_id=ALPHA_ORGANIZATION_ID,
                    actor_id=ALPHA_USER_ID,
                    event_type="candidate_data.exported",
                    entity_type="assessment",
                    entity_id=assessment_id,
                    metadata_json={"source": "synthetic-concurrency-test"},
                )
            )
            holder.commit()
            pending[0].result(timeout=5)
            assert envelope.model_dump(mode="json") == snapshot
        finally:
            holder.rollback()
    with export_factory() as session:
        assessment = session.get(Assessment, assessment_id)
        assert assessment is not None and assessment.anonymized_at is not None
        assert (
            session.scalar(
                select(AuditEvent.id).where(AuditEvent.event_type == "candidate_data.exported")
            )
            is not None
        )
        with pytest.raises(AccessProblemError) as error:
            service(session).export(assessment_id)
        assert (error.value.status, error.value.code) == (410, "candidate_data_anonymized")


def test_erasure_first_waiting_export_rejects_even_preloaded_state(
    export_factory: sessionmaker[Session],
) -> None:
    assessment_id, _ = candidate_record(export_factory, with_report=True)
    pid: Queue[int] = Queue()

    def export() -> AccessProblemError:
        with export_factory() as session:
            stale = session.get(Assessment, assessment_id)
            assert stale is not None and stale.anonymized_at is None
            pid.put(session.scalar(text("SELECT pg_backend_pid()")))
            with pytest.raises(AccessProblemError) as error:
                service(session).export(assessment_id)
            return error.value

    with export_factory() as holder, ThreadPoolExecutor(max_workers=1) as executor:
        holder.info[REQUEST_TRANSACTION_INFO_KEY] = True
        try:
            service(holder).anonymize(assessment_id)
            pending = executor.submit(export)
            assert_blocked(holder, pid.get(timeout=5))
            assert not pending.done()
            holder.commit()
            error = pending.result(timeout=5)
            assert (error.status, error.code) == (410, "candidate_data_anonymized")
        finally:
            holder.rollback()


def test_postgres_api_export_preserves_audit_headers_and_tenant_hiding(
    export_factory: sessionmaker[Session],
) -> None:
    own_id, _ = candidate_record(export_factory, with_report=True)
    foreign_id, _ = candidate_record(export_factory, organization="beacon", with_report=True)
    application = create_app(
        session_factory=export_factory,
        authentication_settings=AuthenticationSettings(
            jwt_secret=SECRET, jwt_issuer=ISSUER, jwt_audience=AUDIENCE
        ),
        invitation_settings=InvitationSettings(token_signing_secret=SECRET),
    )
    auth = headers(ADMIN_SUBJECT, ALPHA_ORGANIZATION_ID)
    with TestClient(application) as client:
        exported = client.post(f"/v1/candidates/{own_id}/export", headers=auth)
        assert exported.status_code == 200
        assert exported.headers["cache-control"] == "no-store"
        assert "attachment" in exported.headers["content-disposition"]
        assert exported.json()["schema_version"] == "1.0"
        foreign = client.post(f"/v1/candidates/{foreign_id}/export", headers=auth)
        missing = client.post(f"/v1/candidates/{uuid4()}/export", headers=auth)
        assert foreign.status_code == missing.status_code == 404
        for key in ("code", "detail", "title"):
            assert foreign.json()[key] == missing.json()[key]
        assert client.delete(f"/v1/candidates/{own_id}", headers=auth).status_code == 200
        erased = client.post(f"/v1/candidates/{own_id}/export", headers=auth)
        assert erased.status_code == 410
        assert erased.json()["code"] == "candidate_data_anonymized"
    with export_factory() as session:
        assert (
            session.scalar(
                select(AuditEvent.id).where(
                    AuditEvent.entity_id == own_id,
                    AuditEvent.event_type == "candidate_data.exported",
                    AuditEvent.metadata_json["outcome"].as_string() == "succeeded",
                )
            )
            is not None
        )
