"""Synthetic privacy discovery contract, isolation and bounded pagination checks."""

from __future__ import annotations

# ruff: noqa: F811 -- fixture parameters intentionally shadow imported fixtures.
import base64
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import event, select
from sqlalchemy.orm import Session, sessionmaker

from app.database.models import Assessment, AuditEvent, InternalUserRole, User
from app.database.seed import (
    ALPHA_ORGANIZATION_ID,
    ALPHA_ROLE_ID,
    ALPHA_USER_ID,
    BEACON_ORGANIZATION_ID,
    BEACON_ROLE_ID,
)
from app.privacy.schemas import PrivacyDiscoveryResponse
from tests.test_privacy import (  # noqa: F401
    ADMIN_SUBJECT,
    BEACON_ADMIN_SUBJECT,
    anyio_backend,
    candidate_record,
    headers,
    privacy_client,
    privacy_factory,
)

PATH = "/v1/privacy/assessments"
AUTH = headers(ADMIN_SUBJECT, ALPHA_ORGANIZATION_ID)
NOW = datetime(2026, 11, 4, 12, tzinfo=UTC)
FIXTURES = Path(__file__).parent / "fixtures" / "privacy_discovery"


def seed(factory: sessionmaker[Session], count: int) -> list[UUID]:
    ids = [candidate_record(factory)[0] for _ in range(count)]
    with factory() as session:
        for assessment_id in ids:
            row = session.get(Assessment, assessment_id)
            assert row is not None
            row.created_at = NOW
        session.commit()
    return sorted(ids, reverse=True)


@pytest.mark.anyio
async def test_canonical_fixture_and_invitation_lookup(
    privacy_client: AsyncClient, privacy_factory: sessionmaker[Session]
) -> None:
    assessment_id = seed(privacy_factory, 1)[0]
    expected = json.loads((FIXTURES / "page.json").read_text())
    with privacy_factory() as session:
        row = session.get(Assessment, assessment_id)
        assert row is not None
        row.id = UUID(expected["items"][0]["assessment_id"])
        row.submitted_at = NOW
        row.retention_expires_at = NOW + timedelta(days=30)
        invitation_id = row.invite_id
        session.commit()
    response = await privacy_client.get(
        PATH, headers=AUTH, params={"invitation_id": str(invitation_id)}
    )
    assert response.status_code == 200
    assert response.json() == expected
    assert response.headers["cache-control"] == "no-store"
    assert PrivacyDiscoveryResponse.model_validate(expected).schema_version == "1.0"


@pytest.mark.anyio
async def test_pages_ties_anonymized_and_minimal_sql(
    privacy_client: AsyncClient, privacy_factory: sessionmaker[Session]
) -> None:
    ids = seed(privacy_factory, 5)
    with privacy_factory() as session:
        row = session.get(Assessment, ids[0])
        assert row is not None
        row.anonymized_at = NOW
        session.commit()
    engine = privacy_factory.kw["bind"]
    statements: list[str] = []

    def capture(
        conn: object,
        cursor: object,
        statement: str,
        parameters: object,
        context: object,
        executemany: bool,
    ) -> None:
        if "FROM assessments" in statement:
            statements.append(statement)

    event.listen(engine, "before_cursor_execute", capture)
    try:
        seen: list[str] = []
        cursor = None
        while True:
            params = {"role_id": str(ALPHA_ROLE_ID), "limit": "2"}
            if cursor:
                params["cursor"] = cursor
            response = await privacy_client.get(PATH, headers=AUTH, params=params)
            assert response.status_code == 200
            body = response.json()
            seen.extend(item["assessment_id"] for item in body["items"])
            assert set(body["items"][0]) == {
                "assessment_id",
                "created_at",
                "submitted_at",
                "retention_expires_at",
                "anonymized_at",
            }
            if cursor is None:
                assert body["items"][0]["anonymized_at"] is not None
            cursor = body["next_cursor"]
            if cursor is None:
                break
            assert len(cursor) == 103
        assert seen == list(map(str, ids))
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    assert len(statements) == 5  # Three limited pages and two unique anchor lookups.
    assert sum("LIMIT" in statement for statement in statements) == 3
    assert all(
        "scores_json" not in s and "responses_json" not in s and "email" not in s
        for s in statements
    )
    with privacy_factory() as session:
        audits = session.scalars(
            select(AuditEvent).where(AuditEvent.event_type == "privacy.assessments_discovered")
        ).all()
        assert len(audits) == 3
        assert all(a.entity_id == ALPHA_USER_ID for a in audits)
        assert all(
            set(a.metadata_json) == {"http_method", "http_status", "outcome"} for a in audits
        )


@pytest.mark.anyio
async def test_empty_unknown_foreign_and_unsubmitted(
    privacy_client: AsyncClient, privacy_factory: sessionmaker[Session]
) -> None:
    foreign_id, _ = candidate_record(privacy_factory, organization="beacon")
    with privacy_factory() as session:
        row = session.get(Assessment, foreign_id)
        assert row is not None
        foreign_invite = row.invite_id
    expected = json.loads((FIXTURES / "empty.json").read_text())
    for params in [
        {"role_id": str(ALPHA_ROLE_ID)},
        {"role_id": str(BEACON_ROLE_ID)},
        {"role_id": str(uuid4())},
        {"invitation_id": str(foreign_invite)},
        {"invitation_id": str(uuid4())},
    ]:
        response = await privacy_client.get(PATH, headers=AUTH, params=params)
        assert response.status_code == 200
        assert response.json() == expected
    seed(privacy_factory, 1)
    response = await privacy_client.get(PATH, headers=AUTH, params={"role_id": str(ALPHA_ROLE_ID)})
    assert response.json()["items"][0]["submitted_at"] is None


@pytest.mark.anyio
@pytest.mark.parametrize("role", [InternalUserRole.RECRUITER, InternalUserRole.HIRING_MANAGER])
async def test_permissions(
    privacy_client: AsyncClient, privacy_factory: sessionmaker[Session], role: InternalUserRole
) -> None:
    with privacy_factory() as session:
        user = session.get(User, ALPHA_USER_ID)
        assert user is not None
        user.role = role
        session.commit()
    response = await privacy_client.get(PATH, headers=AUTH, params={"role_id": str(ALPHA_ROLE_ID)})
    assert response.status_code == 403
    assert response.headers["cache-control"] == "no-store"
    response = await privacy_client.get(PATH, params={"role_id": str(ALPHA_ROLE_ID)})
    assert response.status_code == 401
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "params",
    [
        {},
        {"role_id": str(ALPHA_ROLE_ID), "invitation_id": str(uuid4())},
        {"invitation_id": "person@example.invalid"},
        {"role_id": "bad"},
        *[{"role_id": str(ALPHA_ROLE_ID), "limit": value} for value in ["0", "51", "-1", "1.5"]],
        *[{"role_id": str(ALPHA_ROLE_ID), "cursor": value} for value in ["", "?" * 103, "A" * 105]],
    ],
)
async def test_bounds(privacy_client: AsyncClient, params: dict[str, str]) -> None:
    response = await privacy_client.get(PATH, headers=AUTH, params=params)
    assert response.status_code == 422
    assert response.headers["cache-control"] == "no-store"
    assert "person@example.invalid" not in response.text


@pytest.mark.anyio
async def test_cursor_binding_tampering_and_deleted_anchor(
    privacy_client: AsyncClient, privacy_factory: sessionmaker[Session]
) -> None:
    ids = seed(privacy_factory, 3)
    params = {"role_id": str(ALPHA_ROLE_ID), "limit": "1"}
    response = await privacy_client.get(PATH, headers=AUTH, params=params)
    cursor = response.json()["next_cursor"]
    payload = base64.urlsafe_b64decode(cursor + "=")
    with privacy_factory() as session:
        row = session.get(Assessment, ids[0])
        assert row is not None
        invitation_id = row.invite_id
    variants = [
        (
            AUTH,
            {
                **params,
                "cursor": base64.urlsafe_b64encode(b"\x02" + payload[1:]).rstrip(b"=").decode(),
            },
        ),
        (
            AUTH,
            {
                **params,
                "cursor": base64.urlsafe_b64encode(payload[:-1] + b"X").rstrip(b"=").decode(),
            },
        ),
        (
            AUTH,
            {
                **params,
                "cursor": base64.urlsafe_b64encode(payload[:34] + uuid4().bytes + payload[50:])
                .rstrip(b"=")
                .decode(),
            },
        ),
        (AUTH, {"role_id": str(BEACON_ROLE_ID), "cursor": cursor}),
        (AUTH, {"invitation_id": str(invitation_id), "cursor": cursor}),
        (headers(BEACON_ADMIN_SUBJECT, BEACON_ORGANIZATION_ID), {**params, "cursor": cursor}),
    ]
    # A noncanonical encoding with changed unused pad bits must also be rejected.
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    variants.append(
        (AUTH, {**params, "cursor": cursor[:-1] + alphabet[alphabet.index(cursor[-1]) + 1]})
    )
    for auth, query in variants:
        response = await privacy_client.get(PATH, headers=auth, params=query)
        assert response.status_code == 422
        assert response.json()["code"] == "invalid_privacy_cursor"
    with privacy_factory() as session:
        row = session.get(Assessment, ids[0])
        assert row is not None
        session.delete(row)
        session.commit()
    response = await privacy_client.get(PATH, headers=AUTH, params={**params, "cursor": cursor})
    assert response.status_code == 422


@pytest.mark.anyio
async def test_maximum_and_default_page_sizes(
    privacy_client: AsyncClient, privacy_factory: sessionmaker[Session]
) -> None:
    seed(privacy_factory, 51)
    for extra, count in [({}, 20), ({"limit": "50"}, 50)]:
        response = await privacy_client.get(
            PATH, headers=AUTH, params={"role_id": str(ALPHA_ROLE_ID), **extra}
        )
        assert response.status_code == 200
        assert len(response.json()["items"]) == count
        assert response.json()["next_cursor"] is not None
