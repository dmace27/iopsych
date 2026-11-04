"""Populate revision 0007 before upgrading; never use an existing database/schema."""

import os
from collections.abc import Generator
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from ipaddress import ip_address
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from alembic import command
from sqlalchemy import Engine, MetaData, create_engine, select, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError, DBAPIError
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from app.assignments.registry import (
    definition_response,
    legacy_definition,
    read_assignment,
    read_report,
    score_assignment,
)
from app.database.seed import ALPHA_PROFILE_ID, seed_database
from iopsych_contracts import RoleConstructRating as RatingContract
from iopsych_contracts.assessment import AssessmentResponseSet, score_assessment
from iopsych_contracts.matching import (
    MatchingAlgorithmVersion,
    MatchingRoleProfile,
    match_role_profile,
)
from tests.test_database_migrations import alembic_config
from tests.test_reports import responses

APPROVED_UPGRADE_DATABASES = {
    (5620, "iopsych_final"),
    (5550, "iopsych_6c"),
    (5571, "iopsych_regression"),
    (5606, "iopsych_reconcile"),
}


def validated_upgrade_url(database_url: str) -> URL:
    """Accept only explicit synthetic loopback targets, before creating an engine."""
    message = (
        "Upgrade tests require postgresql+psycopg on numeric loopback, "
        "port/database 5550/iopsych_6c or 5571/iopsych_regression, with no URL query"
    )
    try:
        url = make_url(database_url)
        if (
            url.drivername != "postgresql+psycopg"
            or not url.host
            or "%" in url.host
            or not ip_address(url.host).is_loopback
            or (url.port, url.database) not in APPROVED_UPGRADE_DATABASES
            or "?" in database_url
            or "#" in database_url
            or url.query
        ):
            raise ValueError(message)
    except (ArgumentError, ValueError, TypeError):
        raise ValueError(message) from None
    return url


@pytest.fixture(params=["sqlite", "postgresql"])
def upgrade_url(request: pytest.FixtureRequest, tmp_path: Path) -> Generator[str]:
    if request.param == "sqlite":
        yield f"sqlite+pysqlite:///{tmp_path / 'populated-upgrade.db'}"
        return
    database_url = os.environ.get("TEST_POSTGRES_URL", "")
    if not database_url:
        pytest.skip("Isolated PostgreSQL requires explicit TEST_POSTGRES_URL")
    url = validated_upgrade_url(database_url)
    schema = f"assignment_upgrade_{uuid4().hex}"
    admin = create_engine(url)
    with admin.begin() as connection:
        connection.execute(CreateSchema(schema))
    try:
        yield url.update_query_dict({"options": f"-csearch_path={schema}"}).render_as_string(
            hide_password=False
        )
    finally:
        with admin.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        admin.dispose()


def test_populated_upgrade_preserves_assignments_and_original_interpretation(
    upgrade_url: str,
    database_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", upgrade_url)
    config = alembic_config(upgrade_url)
    command.upgrade(config, "20260929_0007")
    engine = create_engine(upgrade_url)
    definition = legacy_definition()
    saved_draft = responses()
    scores = score_assessment(definition, AssessmentResponseSet.model_validate(saved_draft))
    with Session(database_engine) as session:
        seed_database(session)
        session.commit()
    metadata = MetaData()
    metadata.reflect(engine)
    seed_metadata = MetaData()
    seed_metadata.reflect(database_engine)
    with database_engine.connect() as source, engine.begin() as target:
        for table in metadata.sorted_tables:
            if table.name not in seed_metadata.tables:
                continue
            seed_table = seed_metadata.tables[table.name]
            rows = (
                source.execute(select(*(seed_table.c[column.name] for column in table.c)))
                .mappings()
                .all()
            )
            if rows:
                target.execute(table.insert(), [dict(row) for row in rows])
        ratings_table = metadata.tables["role_construct_ratings"]
        ratings = (
            target.execute(
                select(ratings_table).where(ratings_table.c.profile_id == ALPHA_PROFILE_ID.hex)
            )
            .mappings()
            .all()
        )
        result = match_role_profile(
            MatchingRoleProfile(
                approved=True,
                constructs=tuple(
                    RatingContract(
                        key=r["construct_key"],
                        rating=r["rating"],
                        confidence=r["confidence"],
                        rationale=r["rationale"],
                        evidence=r["evidence_json"],
                    )
                    for r in ratings
                ),
            ),
            scores,
            algorithm_version=MatchingAlgorithmVersion.V1,
        ).model_dump(mode="json")
    invites = metadata.tables["assessment_invites"]
    consents = metadata.tables["candidate_consents"]
    assessments = metadata.tables["assessments"]
    reports = metadata.tables["alignment_reports"]
    # Reflected SQLite CHAR UUID columns expect hex strings; PostgreSQL UUID accepts these.
    ids = {
        state: uuid4().hex
        for state in (
            "unopened",
            "consented",
            "expired",
            "submitted",
            "unknown",
            "malformed",
            "anonymized",
        )
    }
    now = datetime.now(UTC)
    before: dict[str, Any] = {}
    report_id = uuid4().hex
    with engine.begin() as connection:
        for state, invite_id in ids.items():
            connection.execute(
                invites.insert().values(
                    id=invite_id,
                    role_profile_id=ALPHA_PROFILE_ID.hex,
                    email=f"{state}@example.invalid",
                    token_hash=uuid4().hex * 2,
                    expires_at=now + timedelta(days=-1 if state == "expired" else 7),
                    status="active" if state == "unopened" else "consented",
                )
            )
            if state == "unopened":
                continue
            consent_id = uuid4().hex
            connection.execute(
                consents.insert().values(
                    id=consent_id,
                    invite_id=invite_id,
                    decision="consent",
                    notice_version="pilot-v1",
                )
            )
            if state in {"consented", "expired"}:
                continue
            assessment_id = uuid4().hex
            definition_payload = definition.model_dump(mode="json")
            if state == "unknown":
                definition_payload["version"] = "99.0.0"
            if state in {"malformed", "anonymized"}:
                definition_payload = {}
            response_payload = {} if state == "anonymized" else deepcopy(saved_draft)
            score_payload = {} if state == "anonymized" else scores.model_dump(mode="json")
            before[state] = (definition_payload, response_payload, score_payload)
            connection.execute(
                assessments.insert().values(
                    id=assessment_id,
                    invite_id=invite_id,
                    consent_id=consent_id,
                    submitted_at=now,
                    definition_json=definition_payload,
                    responses_json=response_payload,
                    scores_json=score_payload,
                    anonymized_at=now if state == "anonymized" else None,
                )
            )
            if state == "submitted":
                connection.execute(
                    reports.insert().values(
                        id=report_id,
                        assessment_id=assessment_id,
                        role_profile_id=ALPHA_PROFILE_ID.hex,
                        algorithm_version="1.0.0",
                        result_json=result,
                    )
                )
    engine.dispose()
    command.upgrade(config, "head")
    engine = create_engine(upgrade_url)
    metadata = MetaData()
    metadata.reflect(engine)
    invites = metadata.tables["assessment_invites"]
    with engine.connect() as connection:
        for state, invite_id in ids.items():
            assignment = connection.scalar(
                select(invites.c.assignment_json).where(invites.c.id == invite_id)
            )
            if state in {"unknown", "malformed", "anonymized"}:
                assert assignment is None
            else:
                assert definition_response(assignment).definition == definition
                assert (
                    score_assignment(
                        read_assignment(assignment),
                        AssessmentResponseSet.model_validate(saved_draft),
                    )
                    == scores
                )
            if state in before:
                row = connection.execute(
                    select(
                        assessments.c.definition_json,
                        assessments.c.responses_json,
                        assessments.c.scores_json,
                    ).where(assessments.c.invite_id == invite_id)
                ).one()
                assert tuple(row) == before[state]
        stored_report = connection.scalar(
            select(reports.c.result_json).where(reports.c.id == report_id)
        )
        assert stored_report == result
        assert read_report("1.0.0", stored_report).model_dump(mode="json") == result
    with engine.begin() as connection:
        connection.execute(
            invites.update().where(invites.c.id == ids["consented"]).values(status="revoked")
        )
    for value in (None, {"replacement": True}):
        with (
            pytest.raises(DBAPIError, match="assignments are immutable"),
            engine.begin() as connection,
        ):
            connection.execute(
                invites.update()
                .where(invites.c.id == ids["submitted"])
                .values(assignment_json=value)
            )
    # NULL history must not silently acquire a guessed assignment either.
    with pytest.raises(DBAPIError, match="assignments are immutable"), engine.begin() as connection:
        connection.execute(
            invites.update()
            .where(invites.c.id == ids["unknown"])
            .values(assignment_json={"replacement": True})
        )
    engine.dispose()
    command.downgrade(config, "20260929_0007")
    engine = create_engine(upgrade_url)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM assessment_invites")) == len(ids)
        assert (
            connection.scalar(select(reports.c.result_json).where(reports.c.id == report_id))
            == result
        )
    engine.dispose()
