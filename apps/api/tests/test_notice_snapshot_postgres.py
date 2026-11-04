"""Populated migration and locking checks confined to fresh synthetic schemas."""

import os
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, MetaData, create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from app.auth.errors import AccessProblemError
from app.database.models import AssessmentInvite, CandidateConsent
from app.database.seed import ALPHA_PROFILE_ID, seed_database
from app.invitations.schemas import CandidateInviteResponse, ConsentRequest
from tests.test_database_migrations import alembic_config
from tests.test_notice_snapshot_api import candidate, legacy


@pytest.fixture
def notice_pg(monkeypatch: pytest.MonkeyPatch) -> Generator[tuple[Engine, Config]]:
    raw = os.environ.get("NOTICE_TEST_POSTGRES_URL")
    if not raw:
        pytest.skip("Requires isolated NOTICE_TEST_POSTGRES_URL")
    url = make_url(raw)
    if (
        url.drivername != "postgresql+psycopg"
        or url.host != "127.0.0.1"
        or (url.port, url.database)
        not in {(5603, "iopsych_notice"), (5606, "iopsych_reconcile"), (5620, "iopsych_final")}
        or url.query
    ):
        raise ValueError("Notice tests require 127.0.0.1:5603/iopsych_notice without overrides")
    schema = f"notice_{uuid4().hex}"
    admin = create_engine(url)
    with admin.begin() as connection:
        connection.execute(CreateSchema(schema))
    target = url.update_query_dict({"options": f"-csearch_path={schema}"})
    target_text = target.render_as_string(hide_password=False)
    monkeypatch.setenv("DATABASE_URL", target_text)
    engine = create_engine(target)
    try:
        yield engine, alembic_config(target_text)
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        admin.dispose()


def test_populated_0010_upgrade_preserves_unknown_history_and_deadlines(
    notice_pg: tuple[Engine, Config], database_engine: Engine
) -> None:
    engine, config = notice_pg
    command.upgrade(config, "20261104_0010")
    with Session(database_engine) as session:
        seed_database(session)
        session.commit()
    metadata, source_metadata = MetaData(), MetaData()
    metadata.reflect(engine)
    source_metadata.reflect(database_engine)
    with database_engine.connect() as source, engine.begin() as target:
        for table in metadata.sorted_tables:
            if table.name not in source_metadata.tables:
                continue
            source_table = source_metadata.tables[table.name]
            rows = (
                source.execute(select(*(source_table.c[c.name] for c in table.c))).mappings().all()
            )
            if rows:
                target.execute(table.insert(), [dict(row) for row in rows])
    now = datetime.now(UTC)
    deadline = now + timedelta(days=17)
    invites = metadata.tables["assessment_invites"]
    consents = metadata.tables["candidate_consents"]
    assessments = metadata.tables["assessments"]
    identifiers = [uuid4() for _ in range(3)]
    with engine.begin() as connection:
        for index, invite_id in enumerate(identifiers):
            connection.execute(
                invites.insert().values(
                    id=invite_id,
                    role_profile_id=ALPHA_PROFILE_ID,
                    email="synthetic@example.invalid",
                    token_hash=f"{index:064x}",
                    expires_at=now + timedelta(days=1),
                    status=["active", "consented", "declined"][index],
                )
            )
            if index:
                consent_id = uuid4()
                connection.execute(
                    consents.insert().values(
                        id=consent_id,
                        invite_id=invite_id,
                        decision="consent" if index == 1 else "decline",
                        notice_version="old-version",
                    )
                )
                if index == 1:
                    connection.execute(
                        assessments.insert().values(
                            id=uuid4(),
                            invite_id=invite_id,
                            consent_id=consent_id,
                            submitted_at=now,
                            retention_expires_at=deadline,
                            definition_json={},
                            responses_json={},
                            scores_json={},
                        )
                    )
    command.upgrade(config, "head")
    with engine.connect() as connection:
        snapshot_rows = connection.execute(
            text(
                "SELECT notice_snapshot_json, notice_sha256, notice_snapshot_origin, "
                "notice_snapshot_recorded_at FROM assessment_invites"
            )
        ).all()
        assert [tuple(row) for row in snapshot_rows] == [(None, None, None, None)] * 3
        assert [
            tuple(row)
            for row in connection.execute(
                text("SELECT notice_version, presented_notice_sha256 FROM candidate_consents")
            ).all()
        ] == [("old-version", None)] * 2
        assert connection.scalar(text("SELECT retention_expires_at FROM assessments")) == deadline
    command.downgrade(config, "20261104_0010")


def test_concurrent_first_get_and_decisions_freeze_one_notice(
    notice_pg: tuple[Engine, Config],
) -> None:
    engine, config = notice_pg
    command.upgrade(config, "head")
    with Session(engine) as session:
        seed_database(session)
        session.commit()
        invite, token = legacy(session)
        invite_id = invite.id
    barrier = Barrier(2)

    def read(days: int) -> CandidateInviteResponse:
        with Session(engine) as session:
            barrier.wait(timeout=10)
            return candidate(session, days).read(token)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(read, days) for days in (37, 365)]
        first, second = [future.result(timeout=15) for future in futures]
    assert first.notice_sha256 == second.notice_sha256
    assert first.consent_notice == second.consent_notice

    def decide(decision: str) -> str:
        with Session(engine) as session:
            barrier.wait(timeout=10)
            try:
                result = candidate(session).record_consent(
                    token,
                    ConsentRequest(decision=decision, presented_notice_sha256=first.notice_sha256),
                )
                assert result.decision is not None
                return result.decision.value
            except AccessProblemError as error:
                return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        decision_futures = [pool.submit(decide, decision) for decision in ("consent", "decline")]
        results = [future.result(timeout=15) for future in decision_futures]
    assert results.count("consent_already_recorded") == 1
    with Session(engine) as session:
        consent = session.scalar(select(CandidateConsent))
        assert consent is not None
        assert consent.presented_notice_sha256 == first.notice_sha256
        stored = session.get(AssessmentInvite, invite_id)
        assert stored is not None and stored.notice_sha256 == first.notice_sha256
    with engine.begin() as connection, pytest.raises(DBAPIError):
        connection.execute(
            text("UPDATE assessment_invites SET notice_sha256 = :digest WHERE id = :id"),
            {"digest": "0" * 64, "id": invite_id},
        )
    with pytest.raises(RuntimeError, match="notice evidence"):
        command.downgrade(config, "20261104_0010")


def test_first_get_races_legacy_post_without_fabricated_digest(
    notice_pg: tuple[Engine, Config],
) -> None:
    engine, config = notice_pg
    command.upgrade(config, "head")
    with Session(engine) as session:
        seed_database(session)
        session.commit()
        _, token = legacy(session)
    barrier = Barrier(2)

    def act(read: bool) -> CandidateInviteResponse:
        with Session(engine) as session:
            barrier.wait(timeout=10)
            service = candidate(session, 37 if read else 365)
            return (
                service.read(token)
                if read
                else service.record_consent(token, ConsentRequest(decision="consent"))
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(act, read) for read in (True, False)]
        read_result, post_result = [future.result(timeout=15) for future in futures]
    assert read_result.notice_sha256 == post_result.notice_sha256
    assert read_result.consent_notice == post_result.consent_notice
    assert post_result.notice_history == "legacy_unverified"
    with Session(engine) as session:
        consent = session.scalar(select(CandidateConsent))
        assert consent is not None and consent.presented_notice_sha256 is None
