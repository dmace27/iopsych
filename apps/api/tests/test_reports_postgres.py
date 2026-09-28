"""Real PostgreSQL locks, migrations, and concurrent report/submission regression tests.

Runs when DATABASE_URL (as in CI) or TEST_POSTGRES_URL names a PostgreSQL database.
Each test owns a random isolated schema; existing application data is never touched.
"""

import asyncio
import os
from collections.abc import Generator
from uuid import uuid4

import pytest
from alembic import command
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema

from app.auth.config import AuthenticationSettings
from app.database.models import AlignmentReport, AlignmentReportItem, Assessment, AuditEvent
from app.database.seed import ALPHA_PROFILE_ID, seed_database
from app.database.session import create_session_factory
from app.invitations.config import InvitationSettings
from app.main import create_app
from tests.test_auth_tokens import AUDIENCE, ISSUER, SECRET
from tests.test_database_migrations import alembic_config
from tests.test_reports import headers, invitation, responses


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def postgres_report_factory(monkeypatch: pytest.MonkeyPatch) -> Generator[sessionmaker[Session]]:
    database_url = os.environ.get("TEST_POSTGRES_URL", os.environ.get("DATABASE_URL", ""))
    if not database_url or make_url(database_url).get_backend_name() != "postgresql":
        pytest.skip("PostgreSQL integration requires TEST_POSTGRES_URL or DATABASE_URL")
    schema = f"report_test_{uuid4().hex}"
    admin_engine = create_engine(database_url)
    with admin_engine.begin() as connection:
        connection.execute(CreateSchema(schema))
    # Never fall back to public: an existing public.alembic_version could make
    # migrations skip this schema and cause the test to touch application tables.
    url = make_url(database_url).update_query_dict({"options": f"-csearch_path={schema}"})
    isolated_url = url.render_as_string(hide_password=False)
    engine = create_engine(url)
    try:
        monkeypatch.setenv("DATABASE_URL", isolated_url)
        command.upgrade(alembic_config(isolated_url), "head")
        factory = create_session_factory(engine)
        with factory() as session:
            seed_database(session)
            session.commit()
        yield factory
        command.downgrade(alembic_config(isolated_url), "base")
    finally:
        engine.dispose()
        with admin_engine.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        admin_engine.dispose()


@pytest.mark.anyio
async def test_concurrent_submissions_and_reports_are_single_snapshots(
    postgres_report_factory: sessionmaker[Session],
) -> None:
    factory = postgres_report_factory
    application = create_app(
        session_factory=factory,
        authentication_settings=AuthenticationSettings(
            jwt_secret=SECRET,
            jwt_issuer=ISSUER,
            jwt_audience=AUDIENCE,
        ),
        invitation_settings=InvitationSettings(token_signing_secret=SECRET),
    )
    token, _ = invitation(factory)
    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        submissions = await asyncio.wait_for(
            asyncio.gather(
                *[
                    client.post(f"/v1/candidate/invites/{token}/submit", json=responses())
                    for _ in range(4)
                ]
            ),
            timeout=30,
        )
        assert all(response.status_code == 201 for response in submissions)
        assessment_ids = {response.json()["assessment_id"] for response in submissions}
        assert len(assessment_ids) == 1
        auth = headers(factory)
        reports = await asyncio.wait_for(
            asyncio.gather(
                *[
                    client.post(
                        "/v1/reports",
                        headers=auth,
                        json={
                            "assessment_id": next(iter(assessment_ids)),
                            "role_profile_id": str(ALPHA_PROFILE_ID),
                        },
                    )
                    for _ in range(4)
                ]
            ),
            timeout=30,
        )
        assert all(response.status_code == 201 for response in reports), [r.text for r in reports]
        assert len({response.json()["id"] for response in reports}) == 1
        assert all(response.json() == reports[0].json() for response in reports)
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(Assessment)) == 1
        assert session.scalar(select(func.count()).select_from(AlignmentReport)) == 1
        assert session.scalar(select(func.count()).select_from(AlignmentReportItem)) == 6
        for event_type in ("assessment.submitted", "alignment_report.generated"):
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(AuditEvent)
                    .where(
                        AuditEvent.event_type == event_type,
                    )
                )
                == 1
            )
