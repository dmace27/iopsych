"""Retained item provenance, access boundaries, and privacy serialization."""

import copy
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.assignments.registry import definition_hash
from app.auth.errors import AccessProblemError
from app.database.models import AlignmentReport, Assessment, AuditEvent
from app.database.seed import ALPHA_PROFILE_ID
from app.reports.trace import build_trace
from app.reports.trace_schemas import ReportTraceV1
from iopsych_contracts.constructs import CONSTRUCT_KEYS
from tests.test_reports import (
    anyio_backend as anyio_backend,
)
from tests.test_reports import (
    headers,
    submitted,
)
from tests.test_reports import (
    report_app as report_app,
)
from tests.test_reports import (
    report_client as report_client,
)
from tests.test_reports import (
    report_factory as report_factory,
)
from tests.test_reports_postgres import postgres_report_factory as postgres_report_factory

FIXTURES = Path(__file__).parent / "fixtures/report_trace"


def source(name: str = "complete") -> dict[str, Any]:
    payload: object = json.loads((FIXTURES / f"{name}.source.json").read_text())
    assert isinstance(payload, dict)
    assert all(isinstance(key, str) for key in payload)
    return payload


@pytest.mark.parametrize("name", ["complete", "skipped", "two-skipped", "all-skipped"])
def test_language_neutral_fixtures_are_exact_and_complete(name: str) -> None:
    payload = source(name)
    before = copy.deepcopy(payload)
    trace = build_trace(**payload)
    assert trace.model_dump(mode="json") == json.loads(
        (FIXTURES / f"{name}.trace.json").read_text()
    )
    assert ReportTraceV1.model_validate_json(trace.model_dump_json()) == trace
    assert payload == before
    assert tuple(row.construct_key for row in trace.constructs) == CONSTRUCT_KEYS
    all_items = [item for construct in trace.constructs for item in construct.items]
    assert len({item.item_id for item in all_items}) == 24
    for construct, score in zip(
        trace.constructs, payload["scores_json"]["construct_scores"], strict=True
    ):
        assert len(construct.items) == 4
        assert [item.block_position for item in construct.items] == sorted(
            item.block_position for item in construct.items
        )
        assert sum(item.contribution for item in construct.items) == score["raw_score"]
        assert (
            sum(item.choice == "block_skipped" for item in construct.items)
            == score["skipped_item_count"]
        )
        assert construct.rating_threshold.rating == score["rating"]
        assert construct.confidence_rule.level == score["confidence"]
        for item in construct.items:
            if item.choice == "block_skipped":
                assert item.most_like_item_id is None and item.least_like_item_id is None
                assert item.contribution == 0
            else:
                block_items = {row.item_id for row in all_items if row.block_id == item.block_id}
                assert item.most_like_item_id in block_items
                assert item.least_like_item_id in block_items
                assert item.most_like_item_id != item.least_like_item_id


def test_zero_skip_and_zero_unselected_have_distinct_completeness() -> None:
    complete = build_trace(**source())
    skipped = build_trace(**source("skipped"))
    for trace, choice, confidence in [
        (complete, "not_selected", "high"),
        (skipped, "block_skipped", "medium"),
    ]:
        structure = next(c for c in trace.constructs if c.construct_key.value == "structure")
        first = structure.items[0]
        assert first.item_id == "b1-structure"
        assert first.contribution == 0 and first.choice == choice
        assert structure.confidence_rule.level == confidence
    all_skipped = build_trace(**source("all-skipped"))
    assert all(
        c.question_selection.classification.value == "insufficient_evidence"
        for c in all_skipped.constructs
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "statement",
        "rehash",
        "assignment_hash",
        "assignment_definition",
        "assignment_algorithm",
        "foreign_item",
        "same_item",
        "duplicate_block",
        "missing_block",
        "unknown_block",
        "score_raw",
        "score_rating",
        "score_confidence",
        "score_invalid",
        "report_summary",
        "report_definition",
        "question",
        "scoring_shape",
    ],
)
def test_trace_rejects_inconsistent_evidence_without_source_mutation(mutation: str) -> None:
    payload = source()
    if mutation in {"statement", "rehash"}:
        payload["definition_json"]["blocks"][0]["items"][0]["statement"] = "Tampered content."
        if mutation == "rehash":
            payload["assignment_json"]["definition"] = copy.deepcopy(payload["definition_json"])
            payload["assignment_json"]["definition_sha256"] = definition_hash(
                payload["definition_json"]
            )
    elif mutation == "assignment_hash":
        payload["assignment_json"]["definition_sha256"] = "0" * 64
    elif mutation == "assignment_definition":
        payload["assignment_json"]["definition"]["title"] = "Different title"
    elif mutation == "assignment_algorithm":
        payload["assignment_json"]["matching_algorithm_version"] = "2.0.0"
    elif mutation == "foreign_item":
        payload["responses_json"]["responses"][0]["most_like_item_id"] = "b2-ambiguity"
    elif mutation == "same_item":
        response = payload["responses_json"]["responses"][0]
        response["most_like_item_id"] = response["least_like_item_id"]
    elif mutation == "duplicate_block":
        payload["responses_json"]["responses"][1] = payload["responses_json"]["responses"][0]
    elif mutation == "missing_block":
        payload["responses_json"]["responses"].pop()
    elif mutation == "unknown_block":
        payload["responses_json"]["responses"][0]["block_id"] = "foreign-block"
    elif mutation.startswith("score_"):
        key, value = {
            "score_raw": ("raw_score", 1),
            "score_rating": ("rating", 2),
            "score_confidence": ("confidence", "low"),
            "score_invalid": ("answered_item_count", 9),
        }[mutation]
        payload["scores_json"]["construct_scores"][0][key] = value
    elif mutation == "report_summary":
        payload["result_json"]["items"][0]["explanation"]["candidate_response"]["raw_score"] = 1
    elif mutation == "report_definition":
        payload["result_json"]["assessment_definition_version"] = "2.0.0"
    elif mutation == "question":
        payload["result_json"]["items"][0]["interview_questions"]["primary"]["id"] = (
            "wrong.primary.v1"
        )
    elif mutation == "scoring_shape":
        payload["definition_json"]["scoring"] = []
    before = copy.deepcopy(payload)
    with pytest.raises(AccessProblemError) as exc:
        build_trace(**payload)
    assert exc.value.code == "report_trace_inconsistent"
    assert "Tampered" not in exc.value.detail
    assert payload == before


@pytest.mark.parametrize("field", ["definition_json", "responses_json", "scores_json"])
def test_absent_legacy_inputs_are_unavailable(field: str) -> None:
    payload = source()
    payload[field] = None
    with pytest.raises(AccessProblemError) as exc:
        build_trace(**payload)
    assert exc.value.code == "report_trace_unavailable"


@pytest.mark.parametrize("field", ["algorithm_version", "definition_version", "scoring_version"])
def test_unknown_versions_fail_closed(field: str) -> None:
    payload = source()
    if field == "algorithm_version":
        payload[field] = "9.0.0"
    elif field == "definition_version":
        payload["definition_json"]["version"] = "9.0.0"
    else:
        payload["definition_json"]["scoring"]["version"] = "9.0.0"
    with pytest.raises(AccessProblemError) as exc:
        build_trace(**payload)
    assert exc.value.code == (
        "unsupported_report_version"
        if field == "algorithm_version"
        else "unsupported_assessment_version"
    )


def test_legacy_unpinned_history_and_saved_prose_are_preserved() -> None:
    payload = source()
    payload["assignment_json"] = None
    payload["result_json"]["items"][0]["interview_questions"]["primary"]["text"] = (
        "Saved historical text."
    )
    with (
        patch(
            "app.assignments.registry.new_assignment",
            side_effect=AssertionError("No eligibility check"),
        ),
        patch(
            "app.assignments.registry.match_role_profile", side_effect=AssertionError("No rematch")
        ),
    ):
        assert build_trace(**payload).report_id == UUID(payload["report_id"])
    trace = build_trace(**payload).model_dump(mode="json")
    trace["extra"] = True
    with pytest.raises(ValidationError):
        ReportTraceV1.model_validate(trace)


async def create_report(
    client: AsyncClient, factory: sessionmaker[Session], *, skipped: bool = False
) -> dict[str, Any]:
    assessment_id = await submitted(client, factory, skipped=skipped)
    response = await client.post(
        "/v1/reports",
        headers=headers(factory),
        json={
            "assessment_id": assessment_id,
            "role_profile_id": str(ALPHA_PROFILE_ID),
        },
    )
    assert response.status_code == 201, response.text
    payload: object = response.json()
    assert isinstance(payload, dict)
    assert all(isinstance(key, str) for key in payload)
    return payload


@pytest.mark.anyio
@pytest.mark.parametrize("skipped", [False, True])
async def test_endpoint_preserves_report_and_audits_without_sensitive_metadata(
    report_client: AsyncClient, report_factory: sessionmaker[Session], skipped: bool
) -> None:
    report = await create_report(report_client, report_factory, skipped=skipped)
    path = f"/v1/reports/{report['id']}"
    auth = headers(report_factory)
    trace = await report_client.get(path + "/trace", headers=auth)
    assert trace.status_code == 200, trace.text
    assert trace.headers["Cache-Control"] == "no-store"
    parsed = ReportTraceV1.model_validate(trace.json())
    assert str(parsed.report_id) == report["id"]
    assert str(parsed.assessment_id) == report["assessment_id"]
    assert (await report_client.get(path, headers=auth)).json() == report
    assert (await report_client.get(path + "/trace")).status_code == 401
    assert (
        await report_client.get(path + "/trace", headers=headers(report_factory, beacon=True))
    ).status_code == 404
    assert (
        await report_client.get(f"/v1/reports/{uuid4()}/trace", headers=auth)
    ).status_code == 404
    with report_factory() as session:
        events = session.scalars(
            select(AuditEvent).where(AuditEvent.event_type == "alignment_report.trace_read")
        ).all()
        assert events
        assert any(
            e.entity_id == UUID(report["id"]) and e.metadata_json["http_status"] == 200
            for e in events
        )
        assert all(
            set(e.metadata_json) == {"http_method", "http_status", "outcome"} for e in events
        )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "mutation,expected",
    [
        ("missing", "report_trace_unavailable"),
        ("tamper", "report_trace_inconsistent"),
        ("anonymized", "candidate_data_anonymized"),
    ],
)
async def test_trace_failure_does_not_repair_or_break_readable_report(
    report_client: AsyncClient, report_factory: sessionmaker[Session], mutation: str, expected: str
) -> None:
    report = await create_report(report_client, report_factory)
    with report_factory() as session:
        assessment = session.get(Assessment, UUID(report["assessment_id"]))
        assert assessment is not None
        if mutation == "missing":
            assessment.responses_json = {}
        elif mutation == "tamper":
            changed = copy.deepcopy(assessment.definition_json)
            changed["blocks"][0]["items"][0]["statement"] = "Tampered content."
            assessment.definition_json = changed
        else:
            assessment.anonymized_at = datetime.now(UTC)
        session.commit()
    path = f"/v1/reports/{report['id']}"
    trace = await report_client.get(path + "/trace", headers=headers(report_factory))
    assert trace.status_code == (410 if mutation == "anonymized" else 409)
    assert trace.json()["code"] == expected
    assert trace.headers["Cache-Control"] == "no-store"
    if mutation != "anonymized":
        assert (await report_client.get(path, headers=headers(report_factory))).json() == report
    with report_factory() as session:
        saved = session.get(AlignmentReport, UUID(report["id"]))
        assert saved is not None and saved.result_json == report["result"]


def test_postgres_trace_and_deletion_serialize_in_both_orders(
    postgres_report_factory: sessionmaker[Session],
) -> None:
    import asyncio
    import time
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    from httpx import ASGITransport
    from sqlalchemy import text

    from app.audit import AuditMiddleware
    from app.auth.config import AuthenticationSettings
    from app.invitations.config import InvitationSettings
    from app.main import create_app
    from app.privacy.config import PrivacySettings
    from app.privacy.service import PrivacyService
    from tests.test_auth_tokens import AUDIENCE, ISSUER, SECRET

    factory = postgres_report_factory
    application = create_app(
        session_factory=factory,
        authentication_settings=AuthenticationSettings(
            jwt_secret=SECRET, jwt_issuer=ISSUER, jwt_audience=AUDIENCE
        ),
        invitation_settings=InvitationSettings(token_signing_secret=SECRET),
    )

    async def setup() -> dict[str, Any]:
        async with AsyncClient(
            transport=ASGITransport(app=application), base_url="http://test"
        ) as client:
            return await create_report(client, factory)

    async def fetch(report_id: str) -> Any:
        async with AsyncClient(
            transport=ASGITransport(app=application), base_url="http://test"
        ) as client:
            return await client.get(f"/v1/reports/{report_id}/trace", headers=headers(factory))

    def delete(assessment_id: str) -> Any:
        with factory() as session:
            return PrivacyService(session, PrivacySettings()).anonymize(UUID(assessment_id))

    def assert_database_waiter() -> None:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            with factory() as session:
                waiting = session.scalar(
                    text(
                        "SELECT count(*) FROM pg_stat_activity "
                        "WHERE datname = current_database() "
                        "AND cardinality(pg_blocking_pids(pid)) > 0"
                    )
                )
                if waiting:
                    return
            time.sleep(0.01)
        raise AssertionError("Expected a real PostgreSQL lock waiter")

    first = asyncio.run(setup())
    reached = Event()
    release = Event()
    original_stage = AuditMiddleware._stage_event

    def paused_audit(self: Any, request: Any, **kwargs: Any) -> bool:
        if request.url.path.endswith("/trace") and kwargs["status_code"] == 200:
            reached.set()
            assert release.wait(15)
        return original_stage(self, request, **kwargs)

    with (
        ThreadPoolExecutor(max_workers=2) as executor,
        patch.object(AuditMiddleware, "_stage_event", paused_audit),
    ):
        trace_future = executor.submit(asyncio.run, fetch(first["id"]))
        try:
            assert reached.wait(10)
            delete_future = executor.submit(delete, first["assessment_id"])
            assert_database_waiter()
            assert not delete_future.done()
        finally:
            release.set()
        trace_response = trace_future.result(timeout=15)
        deletion = delete_future.result(timeout=15)
    assert trace_response.status_code == 200
    assert len(ReportTraceV1.model_validate(trace_response.json()).constructs) == 6
    assert deletion.reports_deleted == 1
    assert asyncio.run(fetch(first["id"])).status_code == 404

    second = asyncio.run(setup())
    reached.clear()
    release.clear()
    original_anonymize = PrivacyService._anonymize_record

    def paused_deletion(self: Any, record: Any, **kwargs: Any) -> Any:
        reached.set()
        assert release.wait(15)
        return original_anonymize(self, record, **kwargs)

    with (
        ThreadPoolExecutor(max_workers=2) as executor,
        patch.object(PrivacyService, "_anonymize_record", paused_deletion),
    ):
        delete_future = executor.submit(delete, second["assessment_id"])
        try:
            assert reached.wait(10)
            trace_future = executor.submit(asyncio.run, fetch(second["id"]))
            assert_database_waiter()
            assert not trace_future.done()
        finally:
            release.set()
        assert delete_future.result(timeout=15).reports_deleted == 1
        denied = trace_future.result(timeout=15)
    assert denied.status_code in (404, 410)
    assert "constructs" not in denied.json()
    with factory() as session:
        assessment = session.get(Assessment, UUID(second["assessment_id"]))
        assert assessment is not None and assessment.anonymized_at is not None
        assert session.get(AlignmentReport, UUID(second["id"])) is None


@pytest.mark.parametrize(
    "raw,expected_rating",
    [(-4, 1), (-3, 1), (-2, 2), (-1, 2), (0, 3), (1, 4), (2, 4), (3, 5), (4, 5)],
)
def test_all_inclusive_threshold_boundaries(raw: int, expected_rating: int) -> None:
    from app.assignments.registry import legacy_definition
    from iopsych_contracts import RoleConstructRating
    from iopsych_contracts.assessment import AssessmentResponseSet, score_assessment
    from iopsych_contracts.matching import MatchingRoleProfile, match_role_profile

    payload = source()
    definition = legacy_definition()
    remaining = abs(raw)
    for block, response in zip(
        definition.blocks, payload["responses_json"]["responses"], strict=True
    ):
        target = next(
            (item for item in block.items if item.construct_key.value == "autonomy"), None
        )
        if target is None:
            continue
        others = [item for item in block.items if item != target]
        response["most_like_item_id"] = others[0].id
        response["least_like_item_id"] = others[1].id
        if remaining:
            response["most_like_item_id" if raw > 0 else "least_like_item_id"] = target.id
            remaining -= 1
    scores = score_assessment(
        definition, AssessmentResponseSet.model_validate(payload["responses_json"])
    )
    role = MatchingRoleProfile(
        approved=True,
        constructs=tuple(
            RoleConstructRating(
                key=key,
                rating=3,
                confidence="low",
                rationale="Synthetic role.",
                evidence=["Synthetic quote."],
            )
            for key in CONSTRUCT_KEYS
        ),
    )
    result = match_role_profile(role, scores)
    payload["scores_json"] = scores.model_dump(mode="json")
    payload["result_json"] = result.model_dump(mode="json")
    trace = build_trace(**payload)
    autonomy = trace.constructs[0]
    assert sum(item.contribution for item in autonomy.items) == raw
    assert autonomy.rating_threshold.rating == expected_rating
    assert (
        autonomy.rating_threshold.minimum_raw_score
        <= raw
        <= autonomy.rating_threshold.maximum_raw_score
    )
    assert all(
        construct.question_selection.classification.value == "insufficient_evidence"
        for construct in trace.constructs
    )
    assert all(construct.confidence_rule.level == "high" for construct in trace.constructs)


@pytest.mark.anyio
async def test_trace_all_report_roles_and_authorization_denials(
    report_client: AsyncClient, report_factory: sessionmaker[Session]
) -> None:
    from app.database.models import InternalUserRole, User
    from app.database.seed import ALPHA_USER_ID, BEACON_ORGANIZATION_ID
    from tests.test_auth_tokens import make_token
    from tests.test_reports import invitation

    report = await create_report(report_client, report_factory)
    path = f"/v1/reports/{report['id']}/trace"
    for role in InternalUserRole:
        with report_factory() as session:
            user = session.get(User, ALPHA_USER_ID)
            assert user is not None
            user.role = role
            subject = user.auth_subject
            session.commit()
        assert (await report_client.get(path, headers=headers(report_factory))).status_code == 200
    foreign_claim = make_token(
        claims={"sub": subject, "organization_id": str(BEACON_ORGANIZATION_ID)}
    )
    assert (
        await report_client.get(path, headers={"Authorization": f"Bearer {foreign_claim}"})
    ).status_code == 401
    candidate_token, _ = invitation(report_factory)
    assert (
        await report_client.get(path, headers={"Authorization": f"Bearer {candidate_token}"})
    ).status_code == 401


@pytest.mark.anyio
async def test_trace_fails_closed_if_required_audit_cannot_commit(
    report_client: AsyncClient, report_factory: sessionmaker[Session]
) -> None:
    from sqlalchemy.exc import SQLAlchemyError

    from app.audit import AuditMiddleware

    report = await create_report(report_client, report_factory)
    auth = headers(report_factory)
    original_stage = AuditMiddleware._stage_event

    def failed_commit(self: Any, request: Any, **kwargs: Any) -> bool:
        staged = original_stage(self, request, **kwargs)
        kwargs["session"].commit = lambda: (_ for _ in ()).throw(
            SQLAlchemyError("Synthetic failure")
        )
        return staged

    with patch.object(AuditMiddleware, "_stage_event", failed_commit):
        response = await report_client.get(f"/v1/reports/{report['id']}/trace", headers=auth)
    assert response.status_code == 500
    assert response.json()["code"] == "audit_persistence_failed"
    assert "constructs" not in response.json()
    assert (await report_client.get(f"/v1/reports/{report['id']}", headers=auth)).json() == report
