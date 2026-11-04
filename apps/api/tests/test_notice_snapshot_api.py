"""Frozen notices, compatible consent, and retained evidence using synthetic data."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import Engine, func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.assignments.registry import new_assignment
from app.auth.context import AuthorizationContext, OrganizationScope
from app.auth.errors import AccessProblemError
from app.database.models import (
    Assessment,
    AssessmentInvite,
    AssessmentInviteStatus,
    AuditEvent,
    CandidateConsent,
    ConsentDecision,
    InternalUserRole,
)
from app.database.seed import ALPHA_ORGANIZATION_ID, ALPHA_PROFILE_ID, ALPHA_ROLE_ID, ALPHA_USER_ID
from app.database.session import create_session_factory
from app.invitations.schemas import ConsentRequest, InvitationCreateRequest
from app.invitations.service import CandidateInvitationService, InternalInvitationService
from app.invitations.tokens import InviteTokenCodec
from app.privacy.config import PrivacySettings
from app.privacy.service import PrivacyService
from iopsych_contracts.assessment import AssessmentResponseSet
from tests.test_invitations import INVITE_SECRET, RecordingDelivery, build_app, invitation_settings
from tests.test_reports import responses


def context() -> AuthorizationContext:
    return AuthorizationContext(
        user_id=ALPHA_USER_ID,
        organization=OrganizationScope(ALPHA_ORGANIZATION_ID),
        email="synthetic@example.invalid",
        name="Synthetic",
        role=InternalUserRole.ADMIN,
    )


def candidate(session: Session, days: int = 90, **settings: object) -> CandidateInvitationService:
    return CandidateInvitationService(
        session,
        invitation_settings(**settings),
        InviteTokenCodec(INVITE_SECRET),
        PrivacySettings(retention_days=days),
    )


def legacy(session: Session) -> tuple[AssessmentInvite, str]:
    token = InviteTokenCodec(INVITE_SECRET).generate()
    invite = AssessmentInvite(
        role_profile_id=ALPHA_PROFILE_ID,
        email="synthetic-candidate@example.invalid",
        token_hash=token.token_hash,
        expires_at=datetime.now(UTC) + timedelta(days=1),
        status=AssessmentInviteStatus.ACTIVE,
        assignment_json=new_assignment(allow_synthetic=True),
    )
    session.add(invite)
    session.commit()
    return invite, token.raw_token


def test_issuance_freezes_config_and_candidate_response_excludes_identity(
    seeded_session: Session,
) -> None:
    delivery = RecordingDelivery()
    service = InternalInvitationService(
        seeded_session,
        context(),
        invitation_settings(),
        InviteTokenCodec(INVITE_SECRET),
        delivery,
        privacy_settings=PrivacySettings(retention_days=37),
    )
    invite = service.create(
        ALPHA_ROLE_ID,
        InvitationCreateRequest(
            role_profile_id=ALPHA_PROFILE_ID, email="synthetic-candidate@example.invalid"
        ),
    )
    assert invite.notice_snapshot_origin == "issued"
    assert invite.notice_snapshot_json is not None
    assert invite.notice_snapshot_json["retention_days"] == 37
    assert invite.notice_sha256 is not None
    token = delivery.messages[0].text_body.split("/invites/")[1].split()[0]
    response = candidate(seeded_session, 120, purpose_statement="Changed purpose").read(token)
    assert response.consent_notice.purpose != "Changed purpose"
    assert response.notice_sha256 == invite.notice_sha256
    assert response.notice_history == "not_recorded"
    assert invite.email not in response.model_dump_json()
    assert token not in response.model_dump_json()


def test_digest_mismatch_has_no_decision_or_audit_write(seeded_session: Session) -> None:
    invite, token = legacy(seeded_session)
    service = candidate(seeded_session)
    first = service.read(token)
    count = seeded_session.scalar(select(func.count()).select_from(AuditEvent))
    with pytest.raises(AccessProblemError) as error:
        service.record_consent(
            token, ConsentRequest(decision="consent", presented_notice_sha256="0" * 64)
        )
    assert error.value.code == "notice_review_required"
    assert seeded_session.scalar(select(func.count()).select_from(CandidateConsent)) == 0
    assert seeded_session.scalar(select(func.count()).select_from(AuditEvent)) == count
    assert invite.status == AssessmentInviteStatus.ACTIVE
    accepted = service.record_consent(
        token, ConsentRequest(decision="consent", presented_notice_sha256=first.notice_sha256)
    )
    assert accepted.notice_history == "digest_recorded"
    assert service.record_consent(token, ConsentRequest(decision="consent")).notice_history == (
        "digest_recorded"
    )


@pytest.mark.parametrize("decision", ["consent", "decline"])
@pytest.mark.parametrize("read_first", [False, True])
def test_old_clients_keep_truthful_history(
    seeded_session: Session, decision: str, read_first: bool
) -> None:
    invite, token = legacy(seeded_session)
    service = candidate(seeded_session)
    if read_first:
        service.read(token)
    result = service.record_consent(token, ConsentRequest(decision=decision))
    assert result.notice_history == "legacy_unverified"
    assert invite.notice_snapshot_origin == ("first_presented" if read_first else "legacy_decision")
    consent = seeded_session.scalar(select(CandidateConsent))
    assert consent is not None and consent.presented_notice_sha256 is None
    assert (
        service.record_consent(
            token, ConsentRequest(decision=decision, presented_notice_sha256=result.notice_sha256)
        ).notice_history
        == "legacy_unverified"
    )


@pytest.mark.parametrize("decision", [ConsentDecision.CONSENT, ConsentDecision.DECLINE])
def test_existing_decisions_never_gain_invented_evidence(
    seeded_session: Session, decision: ConsentDecision
) -> None:
    invite, token = legacy(seeded_session)
    seeded_session.add(
        CandidateConsent(invite_id=invite.id, decision=decision, notice_version="historic")
    )
    seeded_session.commit()
    service = candidate(seeded_session)
    assert service.read(token).notice_history == "legacy_unknown"
    assert service.record_consent(token, ConsentRequest(decision=decision)).notice_sha256 is None
    assert invite.notice_snapshot_json is None
    with pytest.raises(AccessProblemError):
        service.record_consent(
            token, ConsentRequest(decision=decision, presented_notice_sha256="0" * 64)
        )
    assert invite.notice_snapshot_json is None


def test_post_with_digest_before_legacy_presentation_requires_review(
    seeded_session: Session,
) -> None:
    invite, token = legacy(seeded_session)
    with pytest.raises(AccessProblemError):
        candidate(seeded_session).record_consent(
            token, ConsentRequest(decision="consent", presented_notice_sha256="0" * 64)
        )
    assert invite.notice_snapshot_json is None
    assert seeded_session.scalar(select(func.count()).select_from(CandidateConsent)) == 0


@pytest.mark.parametrize("digest", ["A" * 64, "a" * 63, "a" * 65, " " + "a" * 64, 12])
def test_digest_contract_rejects_noncanonical_values(digest: Any) -> None:
    with pytest.raises(ValidationError):
        ConsentRequest(decision="consent", presented_notice_sha256=digest)


def test_tampered_snapshot_fails_closed(seeded_session: Session) -> None:
    invite, token = legacy(seeded_session)
    service = candidate(seeded_session)
    first = service.read(token)
    seeded_session.execute(text("DROP TRIGGER trg_assessment_invites_notice_immutable"))
    assert invite.notice_snapshot_json is not None
    invite.notice_snapshot_json = {**invite.notice_snapshot_json, "retention_days": 999}
    seeded_session.commit()
    actions: tuple[Callable[[], object], ...] = (
        lambda: service.read(token),
        lambda: service.record_consent(
            token, ConsentRequest(decision="consent", presented_notice_sha256=first.notice_sha256)
        ),
        lambda: service.record_consent(token, ConsentRequest(decision="consent")),
    )
    for action in actions:
        with pytest.raises(AccessProblemError) as error:
            action()
        assert error.value.code == "notice_snapshot_invalid"
    assert seeded_session.scalar(select(func.count()).select_from(CandidateConsent)) == 0


def test_retention_and_export_use_snapshot_without_rewriting_deadline(
    seeded_session: Session,
) -> None:
    invite, token = legacy(seeded_session)
    original = candidate(seeded_session, 37).read(token)
    changed = candidate(seeded_session, 365, consent_notice_version="changed")
    accepted = changed.record_consent(
        token, ConsentRequest(decision="consent", presented_notice_sha256=original.notice_sha256)
    )
    assert accepted.consent_notice == original.consent_notice
    assessment_id = changed.submit(token, AssessmentResponseSet.model_validate(responses()))
    assessment = seeded_session.get(Assessment, assessment_id)
    assert assessment is not None and assessment.submitted_at is not None
    assert assessment.retention_expires_at == assessment.submitted_at + timedelta(days=37)
    deadline = assessment.retention_expires_at
    exported = PrivacyService(
        seeded_session, PrivacySettings(retention_days=365), context()
    ).export(assessment_id)
    assert exported.consent.notice_snapshot == invite.notice_snapshot_json
    assert exported.consent.notice_history == "digest_recorded"
    assert exported.consent.presented_notice_sha256 == original.notice_sha256
    assert token not in exported.model_dump_json()
    assert invite.token_hash not in exported.model_dump_json()
    assert changed.submit(token, AssessmentResponseSet.model_validate(responses())) == assessment_id
    assert assessment.retention_expires_at == deadline


def test_capability_header_preserves_exact_legacy_response_keys(seeded_session: Session) -> None:
    _, token = legacy(seeded_session)
    engine = seeded_session.get_bind()
    assert isinstance(engine, Engine)
    factory = create_session_factory(engine)
    with TestClient(build_app(factory, RecordingDelivery())) as client:
        path = f"/v1/candidate/invites/{token}"
        original = client.get(path)
        advertised = client.get(path, headers={"X-IOPsych-Notice-Snapshot": "1"})
        assert original.status_code == advertised.status_code == 200
        old_keys = {
            "invitation_id",
            "organization_name",
            "role_title",
            "expires_at",
            "status",
            "consent_notice",
            "decision",
            "decision_recorded_at",
            "can_start_assessment",
            "assessment_id",
        }
        assert set(original.json()) == old_keys
        assert set(advertised.json()) == old_keys | {"notice_sha256", "notice_history"}
        bad = client.post(
            path + "/consent", json={"decision": "consent", "presented_notice_sha256": "0" * 64}
        )
        assert bad.status_code == 409
        accepted = client.post(
            path + "/consent",
            json={
                "decision": "consent",
                "presented_notice_sha256": advertised.json()["notice_sha256"],
            },
        )
        assert accepted.status_code == 200 and set(accepted.json()) == old_keys
        retry = client.post(
            path + "/consent",
            json={"decision": "consent"},
            headers={"X-IOPsych-Notice-Snapshot": "1"},
        )
        assert retry.json()["notice_history"] == "digest_recorded"


def test_metadata_create_all_rejects_partial_and_late_evidence(seeded_session: Session) -> None:
    invite, _ = legacy(seeded_session)
    with pytest.raises(DBAPIError):
        seeded_session.execute(
            text("UPDATE assessment_invites SET notice_sha256 = :digest WHERE id = :id"),
            {"digest": "0" * 64, "id": invite.id.hex},
        )
    seeded_session.rollback()
    seeded_session.add(
        CandidateConsent(
            invite_id=invite.id, decision=ConsentDecision.CONSENT, notice_version="old"
        )
    )
    seeded_session.commit()
    from app.invitations.service import freeze_notice

    freeze_notice(invite, invitation_settings(), PrivacySettings(), origin="first_presented")
    with pytest.raises(DBAPIError):
        seeded_session.flush()
    seeded_session.rollback()
