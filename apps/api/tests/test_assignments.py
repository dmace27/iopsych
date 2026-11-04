"""Decision-independent assignment compatibility and fail-closed version readers."""

# ruff: noqa: F811 - imported pytest fixtures are injected by parameter name.

from copy import deepcopy
from pathlib import Path
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, sessionmaker

from app.assignments import registry
from app.auth.errors import AccessProblemError
from app.database.models import AlignmentReport, AssessmentInvite, AssessmentInviteStatus
from app.database.seed import ALPHA_PROFILE_ID
from iopsych_contracts.assessment import (
    AssessmentDefinitionStatus,
    AssessmentResponseSet,
    score_assessment,
)
from tests.test_reports import (  # noqa: F401 - shared pytest fixtures
    anyio_backend,
    headers,
    invitation,
    report_app,
    report_client,
    report_factory,
    responses,
    submitted,
)


def test_new_assignments_require_explicit_synthetic_policy(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(AccessProblemError) as denied:
        registry.new_assignment(allow_synthetic=False)
    assert denied.value.code == "assessment_definition_not_assignable"
    original = registry.legacy_definition()
    retired = original.model_copy(update={"status": AssessmentDefinitionStatus.RETIRED})
    monkeypatch.setattr(registry, "legacy_definition", lambda: retired)
    with pytest.raises(AccessProblemError):
        registry.new_assignment(allow_synthetic=True)
    # Retirement and policy changes never strand an existing historical assignment.
    assert registry.read_assignment(registry.snapshot(original)).definition == original
    assert registry.read_assignment(registry.snapshot(retired)).definition == retired


@pytest.mark.parametrize("mutation", ["missing", "hash", "version", "scorer", "matcher", "shape"])
def test_unknown_assignments_fail_closed(mutation: str) -> None:
    payload = registry.new_assignment(allow_synthetic=True)
    if mutation == "missing":
        payload = None  # type: ignore[assignment]
    elif mutation == "hash":
        payload["definition"]["title"] = "Changed content"
    elif mutation == "version":
        payload["definition"]["version"] = "99.0.0"
    elif mutation == "scorer":
        payload["definition"]["scoring"]["version"] = "99.0.0"
    elif mutation == "matcher":
        payload["matching_algorithm_version"] = "99.0.0"
    else:
        payload["contract_version"] = 99
    with pytest.raises(AccessProblemError) as denied:
        registry.read_assignment(payload)
    assert denied.value.code == "unsupported_assessment_version"


@pytest.mark.parametrize("skipped", [False, True])
def test_frozen_assignment_preserves_v1_scoring(skipped: bool) -> None:
    assignment = registry.read_assignment(registry.new_assignment(allow_synthetic=True))
    response = AssessmentResponseSet.model_validate(responses(skipped=skipped))
    assert registry.score_assignment(assignment, response) == score_assessment(
        registry.legacy_definition(), response
    )
    assert registry.definition_hash({"a": 1, "b": 2}) == registry.definition_hash({"b": 2, "a": 1})
    detached = registry.new_assignment(allow_synthetic=True)
    detached["definition"]["title"] = "Local mutation"
    assert registry.new_assignment(allow_synthetic=True)["definition"]["title"] != "Local mutation"


@pytest.mark.anyio
async def test_endpoint_is_pinned_and_existing_api_shape_is_unchanged(
    report_client: AsyncClient,
    report_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token, invite_id = invitation(report_factory)
    path = f"/v1/candidate/invites/{token}"
    expected = registry.legacy_definition().model_dump(mode="json")
    # Simulate future default content without replacing the retained v1 reader.
    monkeypatch.setattr(registry, "new_assignment", lambda **kwargs: {"future": True})
    result = await report_client.get(path + "/definition")
    assert result.status_code == 200, result.text
    assert result.headers["cache-control"] == "no-store"
    assert result.json()["definition"] == expected
    assert result.json()["assignment"]["definition_sha256"] == registry.LEGACY_SHA256
    assert "assignment" not in (await report_client.get(path)).json()
    with report_factory() as session:
        invite = session.get(AssessmentInvite, invite_id)
        assert invite is not None
        invite.status = AssessmentInviteStatus.ACTIVE
        session.commit()
    denied = await report_client.get(path + "/definition")
    assert denied.status_code == 409
    assert denied.json()["code"] == "candidate_consent_required"
    assert (await report_client.get("/v1/candidate/invites/invalid/definition")).status_code == 404


@pytest.mark.parametrize("bulk", [False, True])
def test_snapshot_is_immutable_in_database(
    report_factory: sessionmaker[Session], bulk: bool
) -> None:
    _, invite_id = invitation(report_factory)
    with report_factory() as session, pytest.raises(DBAPIError, match="assignments are immutable"):
        if bulk:
            session.execute(
                update(AssessmentInvite)
                .where(AssessmentInvite.id == invite_id)
                .values(assignment_json=None)
            )
        else:
            invite = session.get(AssessmentInvite, invite_id)
            assert invite is not None
            changed = deepcopy(invite.assignment_json)
            assert changed is not None
            changed["definition"]["title"] = "Replacement"
            invite.assignment_json = changed
        session.commit()


@pytest.mark.anyio
async def test_report_reader_never_recomputes_and_unknown_version_is_explicit(
    report_client: AsyncClient,
    report_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assessment_id = await submitted(report_client, report_factory)
    auth = headers(report_factory)
    created = await report_client.post(
        "/v1/reports",
        headers=auth,
        json={
            "assessment_id": assessment_id,
            "role_profile_id": str(ALPHA_PROFILE_ID),
        },
    )
    assert created.status_code == 201
    path = f"/v1/reports/{created.json()['id']}"
    monkeypatch.setattr(registry, "MATCHERS", {})
    assert (await report_client.get(path, headers=auth)).json() == created.json()
    with report_factory() as session:
        report = session.get(AlignmentReport, UUID(created.json()["id"]))
        assert report is not None
        report.algorithm_version = "99.0.0"
        session.commit()
    denied = await report_client.get(path, headers=auth)
    assert denied.status_code == 409
    assert denied.json()["code"] == "unsupported_report_version"


@pytest.mark.parametrize("payload", [None, [], {}, {"algorithm_version": "99.0.0"}])
def test_malformed_report_is_explicit(payload: object) -> None:
    with pytest.raises(AccessProblemError) as denied:
        registry.read_report("1.0.0", payload)
    assert denied.value.code == "unsupported_report_version"


def test_corrupted_retained_artifact_fails_loudly(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact = tmp_path / "corrupt.json"
    artifact.write_text('{"unexpected":true}')
    monkeypatch.setattr(registry, "LEGACY_DEFINITION_PATH", artifact)
    with pytest.raises(RuntimeError, match="checksum mismatch"):
        registry.legacy_definition()


def test_stored_score_validation_and_report_validation_are_explicit() -> None:
    with pytest.raises(AccessProblemError) as denied:
        registry.read_scores({})
    assert denied.value.code == "unsupported_assessment_version"
    with pytest.raises(AccessProblemError) as denied:
        registry.read_report("1.0.0", {"algorithm_version": "1.0.0"})
    assert denied.value.code == "unsupported_report_version"
    with pytest.raises(AccessProblemError) as denied:
        registry.read_report("99.0.0", {"algorithm_version": "99.0.0"})
    assert denied.value.code == "unsupported_report_version"


@pytest.mark.anyio
async def test_definition_version_failure_and_submission_mismatch(
    report_client: AsyncClient,
    report_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token, _ = invitation(report_factory)
    path = f"/v1/candidate/invites/{token}"
    wrong = responses()
    wrong["assessment_definition_version"] = "2.0.0"
    denied = await report_client.post(path + "/submit", json=wrong)
    assert denied.status_code == 422
    assert denied.json()["code"] == "invalid_assessment_responses"
    monkeypatch.setattr(registry, "SCORERS", {})
    for result in (
        await report_client.get(path + "/definition"),
        await report_client.post(path + "/submit", json=responses()),
    ):
        assert result.status_code == 409
        assert result.json()["code"] == "unsupported_assessment_version"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "state,code",
    [
        ("expired", "invitation_expired"),
        ("revoked", "invitation_unavailable"),
        ("declined", "candidate_consent_required"),
        ("pending_delivery", "resource_not_found"),
    ],
)
async def test_definition_endpoint_preserves_lifecycle_gates(
    report_client: AsyncClient,
    report_factory: sessionmaker[Session],
    state: str,
    code: str,
) -> None:
    token, invite_id = invitation(report_factory)
    with report_factory() as session:
        invite = session.get(AssessmentInvite, invite_id)
        assert invite is not None
        invite.status = AssessmentInviteStatus(state)
        session.commit()
    denied = await report_client.get(f"/v1/candidate/invites/{token}/definition")
    assert denied.status_code in {404, 409, 410}
    assert denied.json()["code"] == code


@pytest.mark.anyio
async def test_new_invite_is_denied_without_synthetic_opt_in(
    report_client: AsyncClient,
    report_factory: sessionmaker[Session],
) -> None:
    from app.database.seed import ALPHA_ROLE_ID

    denied = await report_client.post(
        f"/v1/roles/{ALPHA_ROLE_ID}/invites",
        headers=headers(report_factory),
        json={"role_profile_id": str(ALPHA_PROFILE_ID), "email": "synthetic@example.invalid"},
    )
    assert denied.status_code == 409
    assert denied.json()["code"] == "assessment_definition_not_assignable"


@pytest.mark.anyio
async def test_report_generation_rejects_score_version_mismatch(
    report_client: AsyncClient,
    report_factory: sessionmaker[Session],
) -> None:
    from app.database.models import Assessment

    assessment_id = await submitted(report_client, report_factory)
    with report_factory() as session:
        assessment = session.get(Assessment, UUID(assessment_id))
        assert assessment is not None
        scores = deepcopy(assessment.scores_json)
        scores["scoring_version"] = "99.0.0"
        assessment.scores_json = scores
        session.commit()
    denied = await report_client.post(
        "/v1/reports",
        headers=headers(report_factory),
        json={
            "assessment_id": assessment_id,
            "role_profile_id": str(ALPHA_PROFILE_ID),
        },
    )
    assert denied.status_code == 409
    assert denied.json()["code"] == "unsupported_assessment_version"
