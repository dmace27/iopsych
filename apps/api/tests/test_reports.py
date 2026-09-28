"""Package 3B persistence, authoritative input gates, and access audits."""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
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
    RoleProfile,
    RoleProfileStatus,
    User,
)
from app.database.seed import (
    ALPHA_ORGANIZATION_ID,
    ALPHA_PROFILE_ID,
    ALPHA_ROLE_ID,
    ALPHA_USER_ID,
    BEACON_ORGANIZATION_ID,
    BEACON_PROFILE_ID,
    BEACON_ROLE_ID,
    BEACON_USER_ID,
    seed_database,
)
from app.database.session import create_session_factory
from app.invitations.config import InvitationSettings
from app.invitations.service import PILOT_DEFINITION_PATH
from app.invitations.tokens import InviteTokenCodec
from app.main import create_app
from iopsych_contracts.assessment import AssessmentDefinition
from tests.test_auth_tokens import AUDIENCE, ISSUER, SECRET, make_token


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def report_factory(database_engine: Engine) -> sessionmaker[Session]:
    factory = create_session_factory(database_engine)
    with factory() as session:
        seed_database(session)
        session.commit()
    return factory


@pytest.fixture
def report_app(report_factory: sessionmaker[Session]) -> FastAPI:
    return create_app(
        session_factory=report_factory,
        authentication_settings=AuthenticationSettings(
            jwt_secret=SECRET,
            jwt_issuer=ISSUER,
            jwt_audience=AUDIENCE,
        ),
        invitation_settings=InvitationSettings(token_signing_secret=SECRET),
    )


@pytest.fixture
async def report_client(report_app: FastAPI) -> AsyncGenerator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=report_app), base_url="http://test"
    ) as client:
        yield client


def headers(factory: sessionmaker[Session], *, beacon: bool = False) -> dict[str, str]:
    with factory() as session:
        user = session.get(User, BEACON_USER_ID if beacon else ALPHA_USER_ID)
        assert user is not None
        token = make_token(
            claims={
                "sub": user.auth_subject,
                "organization_id": str(
                    BEACON_ORGANIZATION_ID if beacon else ALPHA_ORGANIZATION_ID,
                ),
            }
        )
    return {"Authorization": f"Bearer {token}"}


def invitation(factory: sessionmaker[Session]) -> tuple[str, UUID]:
    token = InviteTokenCodec(SECRET).generate()
    with factory() as session:
        invite = AssessmentInvite(
            role_profile_id=ALPHA_PROFILE_ID,
            email="candidate@example.invalid",
            token_hash=token.token_hash,
            expires_at=datetime.now(UTC) + timedelta(days=1),
            status=AssessmentInviteStatus.CONSENTED,
        )
        session.add(invite)
        session.flush()
        session.add(
            CandidateConsent(
                invite_id=invite.id, decision=ConsentDecision.CONSENT, notice_version="1.0.0"
            )
        )
        session.commit()
        return token.raw_token, invite.id


def responses(*, skipped: bool = False) -> dict[str, Any]:
    definition = AssessmentDefinition.model_validate_json(PILOT_DEFINITION_PATH.read_text())
    return {
        "assessment_definition_id": definition.id,
        "assessment_definition_version": definition.version,
        "responses": [
            {
                "block_id": b.id,
                "skipped": skipped,
                "most_like_item_id": None if skipped else b.items[0].id,
                "least_like_item_id": None if skipped else b.items[1].id,
            }
            for b in definition.blocks
        ],
    }


async def submitted(
    client: AsyncClient, factory: sessionmaker[Session], *, skipped: bool = False
) -> str:
    token, _ = invitation(factory)
    response = await client.post(
        f"/v1/candidate/invites/{token}/submit", json=responses(skipped=skipped)
    )
    assert response.status_code == 201, response.text
    assert set(response.json()) == {"assessment_id"}
    return str(response.json()["assessment_id"])


@pytest.mark.anyio
@pytest.mark.parametrize("skipped", [False, True])
async def test_report_persists_matching_snapshot_and_audits(
    report_client: AsyncClient,
    report_factory: sessionmaker[Session],
    skipped: bool,
) -> None:
    assessment_id = await submitted(report_client, report_factory, skipped=skipped)
    payload = {"assessment_id": assessment_id, "role_profile_id": str(ALPHA_PROFILE_ID)}
    auth = headers(report_factory)
    created = await report_client.post("/v1/reports", json=payload, headers=auth)
    assert created.status_code == 201, created.text
    body = created.json()
    assert len(body["result"]["items"]) == 6
    assert body["result"]["role_profile_approved"] is True
    for item in body["result"]["items"]:
        assert item["explanation"]["role"]["evidence"]
        assert item["explanation"]["applied_rule"]["description"]
        assert item["interview_questions"]["primary"]["id"]
        if skipped:
            assert item["classification"] == "insufficient_evidence"
    duplicate = await report_client.post("/v1/reports", json=payload, headers=auth)
    assert duplicate.json() == body
    read = await report_client.get(f"/v1/reports/{body['id']}", headers=auth)
    assert read.json() == body
    with report_factory() as session:
        assert session.scalar(select(func.count()).select_from(AlignmentReport)) == 1
        assert session.scalar(select(func.count()).select_from(AlignmentReportItem)) == 6
        events = session.scalars(
            select(AuditEvent).where(AuditEvent.entity_id == UUID(body["id"]))
        ).all()
        assert {e.event_type for e in events} == {
            "alignment_report.generated",
            "alignment_report.generation_requested",
            "alignment_report.read",
        }
    cross = await report_client.get(
        f"/v1/reports/{body['id']}", headers=headers(report_factory, beacon=True)
    )
    assert cross.status_code == 404
    assert (await report_client.get(f"/v1/reports/{body['id']}")).status_code == 401
    assert (await report_client.get(f"/v1/reports/{uuid4()}", headers=auth)).status_code == 404


@pytest.mark.anyio
@pytest.mark.parametrize(
    "gate,code",
    [
        ("submission", "assessment_not_submitted"),
        ("consent", "candidate_consent_required"),
        ("draft", "profile_not_approved"),
        ("approval", "profile_not_approved"),
        ("mismatch", "report_profile_mismatch"),
        ("cross", "resource_not_found"),
        ("missing", "resource_not_found"),
    ],
)
async def test_report_rejects_invalid_sources(
    report_client: AsyncClient, report_factory: sessionmaker[Session], gate: str, code: str
) -> None:
    assessment_id = await submitted(report_client, report_factory)
    profile_id = ALPHA_PROFILE_ID
    with report_factory() as session:
        assessment = session.get(Assessment, UUID(assessment_id))
        profile = session.get(RoleProfile, ALPHA_PROFILE_ID)
        assert assessment is not None and profile is not None
        if gate == "submission":
            assessment.submitted_at = None
        elif gate == "consent":
            consent = session.get(CandidateConsent, assessment.consent_id)
            assert consent is not None
            consent.decision = ConsentDecision.DECLINE
        elif gate == "draft":
            profile.status = RoleProfileStatus.DRAFT
        elif gate == "approval":
            profile.approved_at = None
        elif gate == "mismatch":
            other = RoleProfile(
                role_id=profile.role_id,
                version=2,
                status=RoleProfileStatus.DRAFT,
                created_by=ALPHA_USER_ID,
            )
            session.add(other)
            session.flush()
            profile_id = other.id
        elif gate == "cross":
            profile_id = BEACON_PROFILE_ID
        elif gate == "missing":
            assessment_id = str(uuid4())
        session.commit()
    response = await report_client.post(
        "/v1/reports",
        headers=headers(report_factory),
        json={"assessment_id": assessment_id, "role_profile_id": str(profile_id)},
    )
    assert response.status_code == (404 if code == "resource_not_found" else 409)
    assert response.json()["code"] == code
    with report_factory() as session:
        assert session.scalar(select(func.count()).select_from(AlignmentReport)) == 0


@pytest.mark.anyio
async def test_submission_requires_valid_consented_complete_one_time_input(
    report_client: AsyncClient,
    report_factory: sessionmaker[Session],
) -> None:
    token, invite_id = invitation(report_factory)
    path = f"/v1/candidate/invites/{token}/submit"
    partial = responses()
    partial["responses"] = []
    assert (await report_client.post(path, json=partial)).status_code == 422
    with report_factory() as session:
        invite = session.get(AssessmentInvite, invite_id)
        assert invite is not None
        invite.status = AssessmentInviteStatus.ACTIVE
        session.commit()
    assert (await report_client.post(path, json=responses())).status_code == 409
    with report_factory() as session:
        invite = session.get(AssessmentInvite, invite_id)
        assert invite is not None
        invite.status = AssessmentInviteStatus.CONSENTED
        session.commit()
    first = await report_client.post(path, json=responses())
    assert first.status_code == 201
    retry = await report_client.post(path, json=responses())
    assert retry.status_code == 201
    assert retry.json() == first.json()
    assert (await report_client.post(path, json=responses(skipped=True))).status_code == 409
    read = await report_client.get(f"/v1/candidate/invites/{token}")
    assert read.json()["assessment_id"] == first.json()["assessment_id"]
    assert (
        await report_client.post("/v1/candidate/invites/invalid/submit", json=responses())
    ).status_code == 404


@pytest.mark.anyio
async def test_report_source_discovery_is_scoped_paginated_and_audited(
    report_client: AsyncClient,
    report_factory: sessionmaker[Session],
) -> None:
    path = f"/v1/roles/{ALPHA_ROLE_ID}/assessments"
    auth = headers(report_factory)
    assert (await report_client.get(path, headers=auth)).json() == []
    assessment_id = await submitted(report_client, report_factory)
    listing = await report_client.get(path, headers=auth)
    assert listing.headers["Cache-Control"] == "no-store"
    assert listing.json()[0]["assessment_id"] == assessment_id
    assert listing.json()[0]["report_id"] is None
    assert set(listing.json()[0]) == {
        "assessment_id",
        "invitation_id",
        "candidate_email",
        "role_profile_id",
        "role_profile_version",
        "submitted_at",
        "report_id",
    }
    assert (await report_client.get(path + "?offset=1&limit=1", headers=auth)).json() == []
    assert (await report_client.get(path + "?limit=101", headers=auth)).status_code == 422
    assert (
        await report_client.get(path, headers=headers(report_factory, beacon=True))
    ).status_code == 404
    assert (await report_client.get(path)).status_code == 401
    assert (
        await report_client.get(f"/v1/roles/{BEACON_ROLE_ID}/assessments", headers=auth)
    ).status_code == 404
    created = await report_client.post(
        "/v1/reports",
        headers=auth,
        json={
            "assessment_id": assessment_id,
            "role_profile_id": str(ALPHA_PROFILE_ID),
        },
    )
    assert (await report_client.get(path, headers=auth)).json()[0]["report_id"] == created.json()[
        "id"
    ]
    with report_factory() as session:
        assert (
            session.scalar(
                select(AuditEvent).where(
                    AuditEvent.event_type == "assessment.submissions_read",
                    AuditEvent.entity_id == ALPHA_ROLE_ID,
                )
            )
            is not None
        )


@pytest.mark.anyio
async def test_reports_preserve_approved_historical_versions_after_expiry(
    report_client: AsyncClient,
    report_factory: sessionmaker[Session],
) -> None:
    assessment_id = await submitted(report_client, report_factory)
    with report_factory() as session:
        assessment = session.get(Assessment, UUID(assessment_id))
        profile = session.get(RoleProfile, ALPHA_PROFILE_ID)
        assert assessment is not None and profile is not None
        invite = session.get(AssessmentInvite, assessment.invite_id)
        assert invite is not None
        invite.expires_at = datetime.now(UTC) - timedelta(days=1)
        profile.status = RoleProfileStatus.SUPERSEDED
        session.commit()
    response = await report_client.post(
        "/v1/reports",
        headers=headers(report_factory),
        json={
            "assessment_id": assessment_id,
            "role_profile_id": str(ALPHA_PROFILE_ID),
        },
    )
    assert response.status_code == 201
    assert response.json()["role_profile_version"] == 1
    with report_factory() as session:
        profile = session.get(RoleProfile, ALPHA_PROFILE_ID)
        assert profile is not None
        profile.approved_by = None
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
    # Historical reads keep the exact stored snapshot rather than recomputing it.
    read = await report_client.get(
        f"/v1/reports/{response.json()['id']}", headers=headers(report_factory)
    )
    assert read.json() == response.json()


@pytest.mark.anyio
async def test_failed_report_audit_rolls_back_all_report_rows(
    report_client: AsyncClient,
    report_factory: sessionmaker[Session],
) -> None:
    assessment_id = await submitted(report_client, report_factory)
    with (
        patch(
            "app.reports.service.AuditEvent", side_effect=RuntimeError("synthetic audit failure")
        ),
        pytest.raises(RuntimeError, match="synthetic audit failure"),
    ):
        await report_client.post(
            "/v1/reports",
            headers=headers(report_factory),
            json={
                "assessment_id": assessment_id,
                "role_profile_id": str(ALPHA_PROFILE_ID),
            },
        )
    with report_factory() as session:
        assert session.scalar(select(func.count()).select_from(AlignmentReport)) == 0
        assert session.scalar(select(func.count()).select_from(AlignmentReportItem)) == 0
    retry = await report_client.post(
        "/v1/reports",
        headers=headers(report_factory),
        json={
            "assessment_id": assessment_id,
            "role_profile_id": str(ALPHA_PROFILE_ID),
        },
    )
    assert retry.status_code == 201
