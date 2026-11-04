"""Related audit contract: optional assessment_id UUID excludes entity_id.

The existing array schema, limit (1..200), offset, before UUID and exact
event_type remain unchanged. An administrator must own the assessment through
its invitation/profile/role. Missing or foreign assessments and cursors outside
the same filtered set return 404; conflicting selectors return 422. Responses
are no-store and reads are audited. Only typed assessment, invitation, consent
and currently linked report events qualify; role/user/sibling events do not.
Deletion retains no report IDs, so this is not complete historical lineage.
No migration or change to legacy entity_id/default filtering is required.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import event, select
from sqlalchemy.orm import Session, sessionmaker

from app.database.models import AlignmentReport, Assessment, AuditEvent
from app.database.seed import ALPHA_ORGANIZATION_ID, ALPHA_ROLE_ID, BEACON_ORGANIZATION_ID
from tests.test_privacy import (
    ADMIN_SUBJECT,
    BEACON_ADMIN_SUBJECT,
    RECRUITER_SUBJECT,
    candidate_record,
    headers,
)

pytest_plugins = ("tests.test_privacy",)
PATH = "/v1/privacy/audit-events"
AUTH = headers(ADMIN_SUBJECT, ALPHA_ORGANIZATION_ID)
NOW = datetime(2026, 11, 4, 12, tzinfo=UTC)


@pytest.fixture
def related_events(privacy_factory: sessionmaker[Session]) -> tuple[UUID, list[UUID], UUID]:
    """Synthetic contract fixture with four entity types and exclusion decoys."""

    assessment_id, _ = candidate_record(privacy_factory, with_report=True)
    sibling_id, _ = candidate_record(privacy_factory, with_report=True)
    with privacy_factory() as session:
        assessment = session.get(Assessment, assessment_id)
        assert assessment is not None
        report_id = session.scalar(
            select(AlignmentReport.id).where(AlignmentReport.assessment_id == assessment_id)
        )
        assert report_id is not None
        pairs = [
            ("assessment", assessment_id),
            ("assessment_invite", assessment.invite_id),
            ("candidate_consent", assessment.consent_id),
            ("alignment_report", report_id),
        ]
        ids = [UUID(int=number) for number in range(1, 5)]
        for event_id, (entity_type, entity_id) in zip(ids, pairs, strict=True):
            session.add(
                AuditEvent(
                    id=event_id,
                    organization_id=ALPHA_ORGANIZATION_ID,
                    event_type="fixture.related",
                    entity_type=entity_type,
                    entity_id=entity_id,
                    created_at=NOW,
                    metadata_json={"synthetic": True},
                )
            )
        for entity_type, entity_id in [
            ("role", ALPHA_ROLE_ID),
            ("assessment", sibling_id),
            *[("user", entity_id) for _, entity_id in pairs],
        ]:
            session.add(
                AuditEvent(
                    organization_id=ALPHA_ORGANIZATION_ID,
                    event_type="fixture.related",
                    entity_type=entity_type,
                    entity_id=entity_id,
                    created_at=NOW,
                    metadata_json={},
                )
            )
        session.add(
            AuditEvent(
                organization_id=BEACON_ORGANIZATION_ID,
                event_type="fixture.related",
                entity_type="assessment",
                entity_id=assessment_id,
                created_at=NOW,
                metadata_json={},
            )
        )
        session.commit()
    return assessment_id, list(reversed(ids)), sibling_id


@pytest.mark.anyio
async def test_contract_scope_pagination_and_audit(
    privacy_client: AsyncClient,
    privacy_factory: sessionmaker[Session],
    related_events: tuple[UUID, list[UUID], UUID],
) -> None:
    assessment_id, ids, _ = related_events
    params = {"assessment_id": str(assessment_id), "event_type": "fixture.related"}
    response = await privacy_client.get(PATH, headers=AUTH, params=params)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert [item["id"] for item in response.json()] == list(map(str, ids))
    assert set(response.json()[0]) == {
        "id",
        "actor_id",
        "event_type",
        "entity_type",
        "entity_id",
        "occurred_at",
        "details",
    }
    first = await privacy_client.get(PATH, headers=AUTH, params={**params, "limit": 2})
    second = await privacy_client.get(
        PATH, headers=AUTH, params={**params, "limit": 2, "before": first.json()[-1]["id"]}
    )
    assert [item["id"] for item in first.json() + second.json()] == list(map(str, ids))
    offset = await privacy_client.get(
        PATH, headers=AUTH, params={**params, "offset": 1, "limit": 1, "before": str(ids[0])}
    )
    assert [item["id"] for item in offset.json()] == [str(ids[2])]
    empty = await privacy_client.get(
        PATH, headers=AUTH, params={**params, "event_type": "fixture.absent"}
    )
    assert empty.json() == []
    with privacy_factory() as session:
        assert (
            session.scalar(
                select(AuditEvent.id).where(
                    AuditEvent.organization_id == ALPHA_ORGANIZATION_ID,
                    AuditEvent.event_type == "privacy.audit_history_read",
                )
            )
            is not None
        )


@pytest.mark.anyio
async def test_authorization_selectors_and_filtered_cursors(
    privacy_client: AsyncClient,
    privacy_factory: sessionmaker[Session],
    related_events: tuple[UUID, list[UUID], UUID],
) -> None:
    assessment_id, ids, sibling_id = related_events
    params = {"assessment_id": str(assessment_id)}
    for auth, expected in [
        ({}, 401),
        (headers(RECRUITER_SUBJECT, ALPHA_ORGANIZATION_ID), 403),
        (headers(BEACON_ADMIN_SUBJECT, BEACON_ORGANIZATION_ID), 404),
    ]:
        response = await privacy_client.get(PATH, headers=auth, params=params)
        assert response.status_code == expected
    with privacy_factory() as session:
        sibling_event = session.scalar(
            select(AuditEvent.id).where(AuditEvent.entity_id == sibling_id)
        )
    cases: list[tuple[dict[str, str | int], int]] = [
        ({"assessment_id": str(uuid4())}, 404),
        ({"entity_id": str(assessment_id)}, 422),
        ({"assessment_id": "invalid"}, 422),
        ({"before": str(uuid4())}, 404),
        ({"before": str(sibling_event)}, 404),
        ({"before": str(ids[0]), "event_type": "fixture.absent"}, 404),
        ({"limit": 201}, 422),
        ({"offset": -1}, 422),
    ]
    for overrides, expected in cases:
        response = await privacy_client.get(PATH, headers=AUTH, params={**params, **overrides})
        assert response.status_code == expected


@pytest.mark.anyio
async def test_deleted_reports_are_not_claimed_as_historical_lineage(
    privacy_client: AsyncClient,
    related_events: tuple[UUID, list[UUID], UUID],
) -> None:
    assessment_id, ids, _ = related_events
    deleted = await privacy_client.delete(f"/v1/candidates/{assessment_id}", headers=AUTH)
    assert deleted.status_code == 200
    assert deleted.json()["reports_deleted"] == 1
    response = await privacy_client.get(
        PATH,
        headers=AUTH,
        params={"assessment_id": str(assessment_id), "event_type": "fixture.related"},
    )
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == list(map(str, ids[1:]))


@pytest.mark.anyio
async def test_bounded_sql_and_legacy_selector_behavior(
    privacy_client: AsyncClient,
    privacy_factory: sessionmaker[Session],
    related_events: tuple[UUID, list[UUID], UUID],
) -> None:
    assessment_id, ids, sibling_id = related_events
    statements: list[str] = []

    def capture(
        conn: object,
        cursor: object,
        statement: str,
        parameters: object,
        context: object,
        executemany: bool,
    ) -> None:
        statements.append(statement)

    engine = privacy_factory.kw["bind"]
    event.listen(engine, "before_cursor_execute", capture)
    try:
        response = await privacy_client.get(
            PATH,
            headers=AUTH,
            params={"assessment_id": str(assessment_id), "limit": 1, "before": str(ids[0])},
        )
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    assert response.status_code == 200
    reads = [sql for sql in statements if sql.startswith("SELECT") and "FROM audit_events" in sql]
    assert len(reads) == 2
    assert all("audit_events.organization_id =" in sql for sql in reads)
    assert all("alignment_reports.assessment_id =" in sql for sql in reads)
    assert "LIMIT" in reads[-1] and "OFFSET" in reads[-1]
    assert not any("assessments.responses_json" in sql for sql in statements)
    legacy = await privacy_client.get(
        PATH,
        headers=AUTH,
        params={"entity_id": str(assessment_id), "event_type": "fixture.related"},
    )
    assert {item["entity_type"] for item in legacy.json()} == {"assessment", "user"}
    legacy_cursor = await privacy_client.get(
        PATH, headers=AUTH, params={"entity_id": str(sibling_id), "before": str(ids[0])}
    )
    assert legacy_cursor.status_code == 200
    default = await privacy_client.get(PATH, headers=AUTH, params={"event_type": "fixture.related"})
    assert len(default.json()) == 10
