"""Candidate export, anonymization, retention, and privacy-admin tests."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.auth.config import AuthenticationSettings
from app.database.models import (
    AlignmentReport,
    AlignmentReportItem,
    Assessment,
    AssessmentInvite,
    AssessmentInviteStatus,
    AuditEvent,
    CandidateConsent,
    ConsentDecision,
    InternalUserRole,
    User,
)
from app.database.seed import (
    ALPHA_ORGANIZATION_ID,
    ALPHA_PROFILE_ID,
    ALPHA_ROLE_ID,
    ALPHA_USER_ID,
    BEACON_ORGANIZATION_ID,
    BEACON_PROFILE_ID,
    BEACON_USER_ID,
    seed_database,
)
from app.database.session import create_session_factory
from app.invitations.config import InvitationSettings
from app.invitations.service import PILOT_DEFINITION_PATH
from app.invitations.tokens import InviteTokenCodec
from app.main import create_app
from app.privacy.config import PrivacySettings
from app.privacy.service import PrivacyService
from iopsych_contracts.assessment import AssessmentDefinition
from tests.test_auth_tokens import AUDIENCE, ISSUER, SECRET, make_token

ADMIN_SUBJECT = "privacy-alpha-admin"
BEACON_ADMIN_SUBJECT = "privacy-beacon-admin"
RECRUITER_ID = UUID("70000000-0000-4000-8000-000000000001")
RECRUITER_SUBJECT = "privacy-alpha-recruiter"
INVITE_SECRET = "privacy-invite-test-secret-with-at-least-32-bytes"


@pytest.fixture
def anyio_backend() -> str:
    """Use asyncio for privacy API tests."""

    return "asyncio"


@pytest.fixture
def privacy_factory(database_engine: Engine) -> sessionmaker[Session]:
    """Seed two admin tenants and one same-tenant non-admin user."""

    factory = create_session_factory(database_engine)
    with factory() as session:
        seed_database(session)
        alpha = session.get(User, ALPHA_USER_ID)
        beacon = session.get(User, BEACON_USER_ID)
        assert alpha is not None and beacon is not None
        alpha.auth_subject = ADMIN_SUBJECT
        alpha.role = InternalUserRole.ADMIN
        beacon.auth_subject = BEACON_ADMIN_SUBJECT
        beacon.role = InternalUserRole.ADMIN
        session.add(
            User(
                id=RECRUITER_ID,
                organization_id=ALPHA_ORGANIZATION_ID,
                email="privacy-recruiter@alpha.example.invalid",
                name="Privacy Recruiter",
                auth_subject=RECRUITER_SUBJECT,
                role=InternalUserRole.RECRUITER,
            )
        )
        session.commit()
    return factory


@pytest.fixture
async def privacy_client(
    privacy_factory: sessionmaker[Session],
) -> AsyncGenerator[AsyncClient]:
    """Provide the fully configured privacy API."""

    app = create_app(
        session_factory=privacy_factory,
        authentication_settings=AuthenticationSettings(
            jwt_secret=SECRET,
            jwt_issuer=ISSUER,
            jwt_audience=AUDIENCE,
        ),
        invitation_settings=InvitationSettings(token_signing_secret=INVITE_SECRET),
        privacy_settings=PrivacySettings(retention_days=30, retention_batch_size=2),
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


def headers(subject: str, organization_id: UUID) -> dict[str, str]:
    """Create one tenant-bound internal bearer credential."""

    token = make_token(claims={"sub": subject, "organization_id": str(organization_id)})
    return {"Authorization": f"Bearer {token}"}


def response_payload() -> dict[str, Any]:
    """Build a complete assessment response payload from the versioned definition."""

    definition = AssessmentDefinition.model_validate_json(
        PILOT_DEFINITION_PATH.read_text(encoding="utf-8")
    )
    return {
        "assessment_definition_id": definition.id,
        "assessment_definition_version": definition.version,
        "responses": [
            {
                "block_id": block.id,
                "skipped": False,
                "most_like_item_id": block.items[0].id,
                "least_like_item_id": block.items[1].id,
            }
            for block in definition.blocks
        ],
    }


def candidate_record(
    factory: sessionmaker[Session],
    *,
    organization: str = "alpha",
    submitted_at: datetime | None = None,
    retention_expires_at: datetime | None = None,
    with_report: bool = False,
) -> tuple[UUID, str]:
    """Persist a candidate chain and return its assessment ID and raw token."""

    profile_id = ALPHA_PROFILE_ID if organization == "alpha" else BEACON_PROFILE_ID
    organization_id = ALPHA_ORGANIZATION_ID if organization == "alpha" else BEACON_ORGANIZATION_ID
    generated = InviteTokenCodec(INVITE_SECRET).generate()
    with factory() as session:
        invite = AssessmentInvite(
            role_profile_id=profile_id,
            email=f"candidate-{uuid4()}@example.invalid",
            token_hash=generated.token_hash,
            expires_at=datetime.now(UTC) + timedelta(days=7),
            status=AssessmentInviteStatus.CONSENTED,
            sent_at=datetime.now(UTC),
        )
        session.add(invite)
        session.flush()
        consent = CandidateConsent(
            invite_id=invite.id,
            decision=ConsentDecision.CONSENT,
            notice_version="pilot-v1",
        )
        session.add(consent)
        session.flush()
        assessment = Assessment(
            invite_id=invite.id,
            consent_id=consent.id,
            submitted_at=submitted_at,
            retention_expires_at=retention_expires_at,
            definition_json={"definition": "retained"},
            responses_json={"responses": ["retained"]},
            scores_json={"scores": ["retained"]},
        )
        session.add(assessment)
        session.flush()
        session.add(
            AuditEvent(
                organization_id=organization_id,
                actor_id=None,
                event_type="assessment.submitted",
                entity_type="assessment",
                entity_id=assessment.id,
                metadata_json={"source": "test"},
            )
        )
        if with_report:
            report = AlignmentReport(
                assessment_id=assessment.id,
                role_profile_id=profile_id,
                algorithm_version="test-v1",
                result_json={"derived": "candidate data"},
            )
            session.add(report)
            session.flush()
            session.add(
                AlignmentReportItem(
                    report_id=report.id,
                    construct_key="autonomy",
                    classification="aligned",
                    confidence="high",
                    explanation_json={"candidate": "derived"},
                    questions_json={"question": "retained"},
                )
            )
        session.commit()
        return assessment.id, generated.raw_token


@pytest.mark.anyio
async def test_admin_export_and_anonymization_are_tenant_scoped_and_audited(
    privacy_client: AsyncClient,
    privacy_factory: sessionmaker[Session],
) -> None:
    """Only admins can export/delete, and deletion erases PII plus derived reports."""

    submitted_at = datetime.now(UTC) - timedelta(days=2)
    assessment_id, raw_token = candidate_record(
        privacy_factory,
        submitted_at=submitted_at,
        retention_expires_at=submitted_at + timedelta(days=30),
        with_report=True,
    )
    path = f"/v1/candidates/{assessment_id}"
    alpha_admin = headers(ADMIN_SUBJECT, ALPHA_ORGANIZATION_ID)
    denied = await privacy_client.post(
        path + "/export",
        headers=headers(RECRUITER_SUBJECT, ALPHA_ORGANIZATION_ID),
    )
    cross_tenant = await privacy_client.post(
        path + "/export",
        headers=headers(BEACON_ADMIN_SUBJECT, BEACON_ORGANIZATION_ID),
    )
    assert denied.status_code == 403
    assert cross_tenant.status_code == 404

    exported = await privacy_client.post(path + "/export", headers=alpha_admin)
    assert exported.status_code == 200
    assert exported.headers["cache-control"] == "no-store"
    assert "attachment" in exported.headers["content-disposition"]
    body = exported.json()
    assert body["assessment"]["id"] == str(assessment_id)
    assert body["assessment"]["created_at"]
    assert body["invitation"]["email"].startswith("candidate-")
    assert body["invitation"]["revoked_at"] is None
    assert body["consent"]["decision"] == "consent"
    assert body["reports"][0]["result"] == {"derived": "candidate data"}
    assert {event["event_type"] for event in body["activity"]} >= {
        "assessment.submitted",
        "candidate_data.exported",
    }

    deleted = await privacy_client.delete(path, headers=alpha_admin)
    assert deleted.status_code == 200
    assert deleted.json()["already_anonymized"] is False
    assert deleted.json()["reports_deleted"] == 1
    assert (await privacy_client.get(f"/v1/candidate/invites/{raw_token}")).status_code == 404
    assert (await privacy_client.post(path + "/export", headers=alpha_admin)).status_code == 410
    repeated = await privacy_client.delete(path, headers=alpha_admin)
    assert repeated.json()["already_anonymized"] is True

    report_attempt = await privacy_client.post(
        "/v1/reports",
        headers=alpha_admin,
        json={
            "assessment_id": str(assessment_id),
            "role_profile_id": str(ALPHA_PROFILE_ID),
        },
    )
    assert report_attempt.status_code == 410
    listing = await privacy_client.get(
        f"/v1/roles/{ALPHA_ROLE_ID}/assessments",
        headers=alpha_admin,
    )
    assert listing.json() == []

    with privacy_factory() as session:
        assessment = session.get(Assessment, assessment_id)
        assert assessment is not None
        invite = session.get(AssessmentInvite, assessment.invite_id)
        assert invite is not None
        assert invite.email.endswith("@privacy.invalid")
        assert invite.status is AssessmentInviteStatus.REVOKED
        assert assessment.responses_json == {"anonymized": True}
        assert (
            session.scalar(
                select(func.count())
                .select_from(AlignmentReport)
                .where(AlignmentReport.assessment_id == assessment_id)
            )
            == 0
        )
        events = list(
            session.scalars(select(AuditEvent).where(AuditEvent.entity_id == assessment_id))
        )
        assert sum(event.event_type == "candidate_data.anonymized" for event in events) == 1
        assert any(event.event_type == "candidate_data.deletion_requested" for event in events)


@pytest.mark.anyio
async def test_retention_status_job_and_audit_lookup_are_bounded_and_tenant_scoped(
    privacy_client: AsyncClient,
    privacy_factory: sessionmaker[Session],
) -> None:
    """Admin and scheduler runs anonymize only due records within their scope and batch."""

    now = datetime.now(UTC)
    due_explicit, _ = candidate_record(
        privacy_factory,
        submitted_at=now - timedelta(days=31),
        retention_expires_at=now - timedelta(days=1),
    )
    due_legacy, _ = candidate_record(
        privacy_factory,
        submitted_at=now - timedelta(days=31),
        retention_expires_at=None,
    )
    future, _ = candidate_record(
        privacy_factory,
        submitted_at=now,
        retention_expires_at=now + timedelta(days=30),
    )
    candidate_record(
        privacy_factory,
        submitted_at=None,
        retention_expires_at=None,
    )
    beacon_due, _ = candidate_record(
        privacy_factory,
        organization="beacon",
        submitted_at=now - timedelta(days=31),
        retention_expires_at=now - timedelta(days=1),
    )
    alpha_admin = headers(ADMIN_SUBJECT, ALPHA_ORGANIZATION_ID)

    status = await privacy_client.get("/v1/privacy/status", headers=alpha_admin)
    assert status.status_code == 200
    assert status.json() == {
        "retention_days": 30,
        "total_assessments": 4,
        "active_assessments": 4,
        "anonymized_assessments": 0,
        "due_assessments": 2,
        "next_retention_at": status.json()["next_retention_at"],
    }
    assert status.json()["next_retention_at"] is not None

    run = await privacy_client.post("/v1/privacy/retention/run", headers=alpha_admin)
    assert set(run.json()["anonymized_assessment_ids"]) == {
        str(due_explicit),
        str(due_legacy),
    }
    filtered = await privacy_client.get(
        f"/v1/privacy/audit-events?entity_id={due_explicit}&event_type=candidate_data.anonymized",
        headers=alpha_admin,
    )
    assert [event["entity_id"] for event in filtered.json()] == [str(due_explicit)]
    first_page = await privacy_client.get(
        "/v1/privacy/audit-events?limit=1",
        headers=alpha_admin,
    )
    cursor = first_page.json()[0]["id"]
    second_page = await privacy_client.get(
        f"/v1/privacy/audit-events?limit=1&before={cursor}",
        headers=alpha_admin,
    )
    assert second_page.status_code == 200
    assert second_page.json()[0]["id"] != cursor
    assert (
        await privacy_client.get(
            f"/v1/privacy/audit-events?before={uuid4()}",
            headers=alpha_admin,
        )
    ).status_code == 404
    assert (
        await privacy_client.get("/v1/privacy/audit-events?limit=0", headers=alpha_admin)
    ).status_code == 422
    refreshed = await privacy_client.get("/v1/privacy/status", headers=alpha_admin)
    assert refreshed.json()["active_assessments"] == 2
    assert refreshed.json()["anonymized_assessments"] == 2

    with privacy_factory() as session:
        assert session.get(Assessment, future).anonymized_at is None  # type: ignore[union-attr]
        assert session.get(Assessment, beacon_due).anonymized_at is None  # type: ignore[union-attr]
        global_result = PrivacyService(
            session,
            PrivacySettings(retention_days=30, retention_batch_size=10),
        ).run_retention(now=now)
        assert global_result.anonymized_assessment_ids == [beacon_due]
        with pytest.raises(RuntimeError, match="organization context"):
            PrivacyService(session, PrivacySettings()).status(now=now)


@pytest.mark.anyio
async def test_submission_stores_configured_retention_deadline(
    privacy_client: AsyncClient,
    privacy_factory: sessionmaker[Session],
) -> None:
    """Candidate submission freezes the configured retention deadline."""

    generated = InviteTokenCodec(INVITE_SECRET).generate()
    with privacy_factory() as session:
        invite = AssessmentInvite(
            role_profile_id=ALPHA_PROFILE_ID,
            email="deadline-candidate@example.invalid",
            token_hash=generated.token_hash,
            expires_at=datetime.now(UTC) + timedelta(days=1),
            status=AssessmentInviteStatus.CONSENTED,
        )
        session.add(invite)
        session.flush()
        session.add(
            CandidateConsent(
                invite_id=invite.id,
                decision=ConsentDecision.CONSENT,
                notice_version="pilot-v1",
            )
        )
        session.commit()
    submitted = await privacy_client.post(
        f"/v1/candidate/invites/{generated.raw_token}/submit",
        json=response_payload(),
    )
    assert submitted.status_code == 201
    landing = await privacy_client.get(f"/v1/candidate/invites/{generated.raw_token}")
    assert landing.json()["consent_notice"]["retention"] == (
        "Pilot data is retained for 30 days after submission, then anonymized."
    )
    with privacy_factory() as session:
        assessment = session.get(Assessment, UUID(submitted.json()["assessment_id"]))
        assert assessment is not None and assessment.submitted_at is not None
        assert assessment.retention_expires_at == assessment.submitted_at + timedelta(days=30)


def test_privacy_settings_and_scheduler_entrypoint_are_safe(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Configuration is bounded and the scheduler prints no candidate identifiers."""

    assert PrivacySettings().retention_days == 90
    for values in (
        {"retention_days": 0},
        {"retention_days": 3651},
        {"retention_batch_size": 0},
        {"retention_batch_size": 1001},
    ):
        with pytest.raises(ValidationError):
            PrivacySettings.model_validate(values)

    fake_result = MagicMock(anonymized_assessment_ids=[uuid4(), uuid4()])
    fake_session = MagicMock(spec=Session)
    fake_context = MagicMock()
    fake_context.__enter__.return_value = fake_session
    fake_factory = MagicMock(return_value=fake_context)
    with (
        patch("app.privacy.retention.create_database_engine"),
        patch("app.privacy.retention.create_session_factory", return_value=fake_factory),
        patch("app.privacy.retention.PrivacyService") as service,
    ):
        service.return_value.run_retention.return_value = fake_result
        from app.privacy.retention import main

        main()
    assert capsys.readouterr().out == "Retention complete: 2 assessments anonymized\n"
