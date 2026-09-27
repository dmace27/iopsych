"""Security, lifecycle, tenant-isolation, and consent tests for package 2B."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from html import escape
from typing import Any, cast
from unittest.mock import patch
from uuid import UUID

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.auth.config import AuthenticationSettings
from app.auth.context import AuthorizationContext, OrganizationScope
from app.auth.errors import AccessProblemError
from app.database.models import (
    AssessmentInvite,
    AssessmentInviteStatus,
    AuditEvent,
    CandidateConsent,
    ConsentDecision,
    InternalUserRole,
    Role,
    RoleProfile,
    RoleProfileStatus,
    RoleStatus,
    User,
)
from app.database.seed import (
    ALPHA_ORGANIZATION_ID,
    ALPHA_PROFILE_ID,
    ALPHA_ROLE_ID,
    ALPHA_USER_ID,
    BEACON_ORGANIZATION_ID,
    BEACON_ROLE_ID,
    BEACON_USER_ID,
    seed_database,
)
from app.database.session import create_session_factory
from app.invitations.config import InvitationSettings
from app.invitations.delivery import (
    InvitationDeliveryError,
    InvitationEmail,
    UnconfiguredInvitationDelivery,
    build_invitation_email,
)
from app.invitations.logging import CandidateInviteTokenFilter, install_invite_token_log_filter
from app.invitations.rate_limit import InMemoryRateLimiter
from app.invitations.schemas import InvitationCreateRequest
from app.invitations.service import InternalInvitationService, require_consented_invite
from app.invitations.tokens import (
    InvalidInviteTokenError,
    InviteTokenCodec,
    opaque_rate_limit_key,
)
from app.main import create_app
from tests.test_auth_tokens import AUDIENCE, ISSUER, SECRET, make_token

INVITE_SECRET = "candidate-invite-test-secret-with-at-least-32-bytes"
BEACON_RECRUITER_SUBJECT = "provider-beacon-recruiter"
DRAFT_PROFILE_ID = UUID("30000000-0000-4000-8000-000000000001")
ARCHIVED_ROLE_ID = UUID("30000000-0000-4000-8000-000000000002")
ARCHIVED_PROFILE_ID = UUID("30000000-0000-4000-8000-000000000003")


class RecordingDelivery:
    """Capture rendered mail without making a network request."""

    def __init__(self) -> None:
        self.messages: list[InvitationEmail] = []

    def send(self, message: InvitationEmail) -> None:
        """Record one message exactly as the provider would receive it."""

        self.messages.append(message)


class FailingDelivery:
    """Simulate a provider failure without exposing provider internals."""

    def send(self, message: InvitationEmail) -> None:
        """Reject every send."""

        del message
        raise InvitationDeliveryError("synthetic provider detail")


@pytest.fixture
def anyio_backend() -> str:
    """Use asyncio for invitation API tests."""

    return "asyncio"


@pytest.fixture
def invitation_session_factory(database_engine: Engine) -> sessionmaker[Session]:
    """Seed approved, draft, archived, and cross-tenant invitation targets."""

    factory = create_session_factory(database_engine)
    with factory() as session:
        seed_database(session)
        alpha = session.get(User, ALPHA_USER_ID)
        beacon = session.get(User, BEACON_USER_ID)
        assert alpha is not None
        assert beacon is not None
        alpha.auth_subject = "provider-alpha-recruiter"
        beacon.auth_subject = BEACON_RECRUITER_SUBJECT
        beacon.role = InternalUserRole.RECRUITER
        session.add(
            RoleProfile(
                id=DRAFT_PROFILE_ID,
                role_id=ALPHA_ROLE_ID,
                version=2,
                status=RoleProfileStatus.DRAFT,
                created_by=ALPHA_USER_ID,
            )
        )
        session.add(
            Role(
                id=ARCHIVED_ROLE_ID,
                organization_id=ALPHA_ORGANIZATION_ID,
                title="Archived Synthetic Role",
                department="Engineering",
                location="Remote",
                job_description="Synthetic archived role.",
                status=RoleStatus.ARCHIVED,
            )
        )
        session.flush()
        session.add(
            RoleProfile(
                id=ARCHIVED_PROFILE_ID,
                role_id=ARCHIVED_ROLE_ID,
                version=1,
                status=RoleProfileStatus.APPROVED,
                created_by=ALPHA_USER_ID,
                approved_by=ALPHA_USER_ID,
                approved_at=datetime.now(UTC),
            )
        )
        session.commit()
    return factory


@pytest.fixture
def delivery() -> RecordingDelivery:
    """Provide an inspectable transactional-email adapter."""

    return RecordingDelivery()


def invitation_settings(**overrides: Any) -> InvitationSettings:
    """Build secure deterministic settings with focused overrides."""

    values: dict[str, Any] = {
        "token_signing_secret": INVITE_SECRET,
        "candidate_base_url": "https://candidate.example.invalid/invites/",
        "default_expiry_hours": 24,
        "maximum_expiry_hours": 48,
        "candidate_rate_limit": 20,
        "internal_rate_limit": 20,
        "rate_window_seconds": 60,
        "privacy_contact_email": "privacy@pilot.example.invalid",
        "accommodation_contact_email": "access@pilot.example.invalid",
    }
    values.update(overrides)
    return InvitationSettings(**values)


def build_app(
    factory: sessionmaker[Session],
    delivery_adapter: RecordingDelivery | FailingDelivery | None,
    *,
    settings: InvitationSettings | None = None,
    limiter: InMemoryRateLimiter | None = None,
) -> FastAPI:
    """Create a fully injected package-2B test application."""

    return create_app(
        authentication_settings=AuthenticationSettings(
            jwt_secret=SECRET,
            jwt_issuer=ISSUER,
            jwt_audience=AUDIENCE,
            jwt_leeway_seconds=0,
        ),
        invitation_settings=settings or invitation_settings(),
        invitation_delivery=delivery_adapter,
        invitation_rate_limiter=limiter,
        session_factory=factory,
    )


@pytest.fixture
async def invitation_client(
    invitation_session_factory: sessionmaker[Session], delivery: RecordingDelivery
) -> AsyncGenerator[AsyncClient]:
    """Provide an in-process secure invitation API client."""

    app = build_app(invitation_session_factory, delivery)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


def auth_header(subject: str, organization_id: UUID) -> dict[str, str]:
    """Issue one signed internal-user credential."""

    token = make_token(claims={"sub": subject, "organization_id": str(organization_id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def alpha_headers() -> dict[str, str]:
    """Authenticate the Alpha recruiter."""

    return auth_header("provider-alpha-recruiter", ALPHA_ORGANIZATION_ID)


@pytest.fixture
def beacon_headers() -> dict[str, str]:
    """Authenticate the isolated Beacon recruiter."""

    return auth_header(BEACON_RECRUITER_SUBJECT, BEACON_ORGANIZATION_ID)


def invite_payload(**overrides: object) -> dict[str, object]:
    """Build valid synthetic invitation input."""

    payload: dict[str, object] = {
        "role_profile_id": str(ALPHA_PROFILE_ID),
        "email": "candidate@synthetic.example.invalid",
        "expires_in_hours": 12,
    }
    payload.update(overrides)
    return payload


def token_from_message(message: InvitationEmail) -> str:
    """Extract the transient token from a captured test-only email."""

    marker = "https://candidate.example.invalid/invites/"
    after_marker = message.text_body.split(marker, maxsplit=1)[1]
    return after_marker.splitlines()[0]


async def create_invite(
    client: AsyncClient,
    headers: dict[str, str],
    delivery_adapter: RecordingDelivery,
    **overrides: object,
) -> tuple[dict[str, Any], str]:
    """Create an invitation and return its safe response plus emailed token."""

    response = await client.post(
        f"/v1/roles/{ALPHA_ROLE_ID}/invites",
        headers=headers,
        json=invite_payload(**overrides),
    )
    assert response.status_code == 201
    return cast(dict[str, Any], response.json()), token_from_message(delivery_adapter.messages[-1])


def test_token_codec_signs_random_tokens_and_only_exposes_one_way_hashes() -> None:
    """Tokens contain 32 random bytes, detect tampering, and hash deterministically."""

    codec = InviteTokenCodec(INVITE_SECRET)
    first = codec.generate()
    second = codec.generate()
    assert first.raw_token != second.raw_token
    assert first.token_hash != second.token_hash
    assert first.raw_token not in first.token_hash
    assert len(first.token_hash) == 64
    assert codec.validate_and_hash(first.raw_token) == first.token_hash
    assert opaque_rate_limit_key(first.raw_token) == first.token_hash

    secret, signature = first.raw_token.split(".")
    tampered_signature = f"{signature[:-1]}{'A' if signature[-1] != 'A' else 'B'}"
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    last_index = alphabet.index(signature[-1])
    noncanonical_signature = f"{signature[:-1]}{alphabet[last_index + 1]}"
    malformed = [
        "",
        "missing-dot",
        "too.many.parts",
        f"{secret}.!",
        f"AA.{signature}",
        f"{secret}.{signature[:-2]}",
        f"{secret}.{tampered_signature}",
        f"{secret}.{noncanonical_signature}",
    ]
    for token in malformed:
        with pytest.raises(InvalidInviteTokenError, match="invalid invite token"):
            codec.validate_and_hash(token)
    with pytest.raises(ValueError, match="at least 32 bytes"):
        InviteTokenCodec("too-short")


def test_settings_schema_delivery_rendering_and_unconfigured_adapter_are_safe() -> None:
    """Configuration is strict and the email template has no assessment-data input."""

    settings = invitation_settings(candidate_base_url=" https://example.test/path/// ")
    assert settings.candidate_base_url == "https://example.test/path"
    with pytest.raises(ValidationError, match="at least 32 bytes"):
        invitation_settings(token_signing_secret="short")
    with pytest.raises(ValidationError, match="cannot exceed"):
        invitation_settings(default_expiry_hours=3, maximum_expiry_hours=2)
    with pytest.raises(ValidationError, match="cannot be blank"):
        invitation_settings(purpose_statement="  ")
    with pytest.raises(ValidationError, match="absolute HTTP"):
        invitation_settings(candidate_base_url="ftp://candidate.example.invalid")
    with pytest.raises(ValidationError, match="query or fragment"):
        invitation_settings(candidate_base_url="https://candidate.example.invalid/path?x=1")
    with pytest.raises(ValidationError, match="use HTTPS"):
        invitation_settings(candidate_base_url="http://candidate.example.invalid/path")

    for invalid_email in ("not-an-email", "one@two@example.invalid"):
        with pytest.raises(ValidationError, match="valid address"):
            InvitationCreateRequest(
                role_profile_id=ALPHA_PROFILE_ID,
                email=invalid_email,
            )
    normalized = InvitationCreateRequest(
        role_profile_id=ALPHA_PROFILE_ID,
        email="Candidate@Example.INVALID",
    )
    assert normalized.email == "Candidate@example.invalid"

    organization = '<Pilot & "Partners">'
    message = build_invitation_email(
        recipient_email="person@example.invalid",
        organization_name=organization,
        invite_url='https://example.invalid/invite/a?next="unsafe"',
        expires_at=datetime(2026, 10, 1, 12, tzinfo=UTC),
        privacy_contact_email="privacy@example.invalid",
    )
    assert message.subject == f"Invitation from {organization}"
    assert "response" not in message.text_body.casefold()
    assert "score" not in message.text_body.casefold()
    assert escape(organization) in message.html_body
    assert "&quot;unsafe&quot;" in message.html_body
    with pytest.raises(InvitationDeliveryError, match="not configured"):
        UnconfiguredInvitationDelivery().send(message)


def test_fixed_window_rate_limiter_resets_and_rejects_invalid_policy() -> None:
    """The limiter returns stable retry hints and discards elapsed windows."""

    now = [100.0]
    limiter = InMemoryRateLimiter(clock=lambda: now[0])
    assert limiter.check("key", limit=2, window_seconds=10).allowed is True
    assert limiter.check("key", limit=2, window_seconds=10).allowed is True
    blocked = limiter.check("key", limit=2, window_seconds=10)
    assert blocked.allowed is False
    assert blocked.retry_after_seconds == 10
    now[0] = 109.2
    assert limiter.check("key", limit=2, window_seconds=10).retry_after_seconds == 1
    now[0] = 110.0
    assert limiter.check("key", limit=2, window_seconds=10).allowed is True
    with pytest.raises(ValueError, match="positive"):
        limiter.check("bad", limit=0, window_seconds=10)


def test_access_logging_redacts_raw_invite_tokens_once() -> None:
    """Default server logs retain route context without persisting bearer values."""

    token = InviteTokenCodec(INVITE_SECRET).generate().raw_token
    path = f"/v1/candidate/invites/{token}/consent?source=email"
    record = logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg='%s - "%s %s HTTP/%s" %d',
        args=("127.0.0.1", "POST", path, "1.1", 200),
        exc_info=None,
    )
    assert CandidateInviteTokenFilter().filter(record) is True
    rendered = record.getMessage()
    assert token not in rendered
    assert "/v1/candidate/invites/[REDACTED]/consent?source=email" in rendered

    mapping_record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=f"candidate path {path}",
        args=({"path": path},),
        exc_info=None,
    )
    CandidateInviteTokenFilter().filter(mapping_record)
    assert token not in str(mapping_record.msg)
    assert token not in str(mapping_record.args)

    logger = logging.getLogger("uvicorn.access")
    before = sum(isinstance(item, CandidateInviteTokenFilter) for item in logger.filters)
    install_invite_token_log_filter()
    install_invite_token_log_filter()
    after = sum(isinstance(item, CandidateInviteTokenFilter) for item in logger.filters)
    assert after == max(1, before)


@pytest.mark.anyio
async def test_invite_consent_happy_path_is_private_hashed_and_audited(
    invitation_client: AsyncClient,
    invitation_session_factory: sessionmaker[Session],
    delivery: RecordingDelivery,
    alpha_headers: dict[str, str],
) -> None:
    """Approved invitations deliver safely and consent is explicit, terminal, and audited."""

    created, token = await create_invite(
        invitation_client, alpha_headers, delivery, email="Person@Synthetic.Example.Invalid"
    )
    assert created["status"] == "active"
    assert created["email"] == "Person@synthetic.example.invalid"
    assert "token" not in created
    assert "token_hash" not in created
    assert len(delivery.messages) == 1
    message = delivery.messages[0]
    assert message.recipient_email == "Person@synthetic.example.invalid"
    assert "score" not in message.text_body.casefold()
    assert "answer" not in message.text_body.casefold()

    landing = await invitation_client.get(f"/v1/candidate/invites/{token}")
    assert landing.status_code == 200
    landing_data = landing.json()
    assert landing_data["organization_name"] == "Alpha Labs (Synthetic)"
    assert landing_data["role_title"] == "Synthetic Platform Engineer"
    assert landing_data["decision"] is None
    assert landing_data["can_start_assessment"] is False
    assert landing_data["consent_notice"]["decline_without_penalty"] is True
    assert "email" not in landing_data
    assert "questions" not in landing_data
    assert "constructs" not in landing_data

    consented = await invitation_client.post(
        f"/v1/candidate/invites/{token}/consent",
        json={"decision": "consent"},
    )
    repeated = await invitation_client.post(
        f"/v1/candidate/invites/{token}/consent",
        json={"decision": "consent"},
    )
    changed = await invitation_client.post(
        f"/v1/candidate/invites/{token}/consent",
        json={"decision": "decline"},
    )
    assert consented.status_code == repeated.status_code == 200
    assert consented.json()["decision"] == "consent"
    assert consented.json()["can_start_assessment"] is True
    assert repeated.json()["decision_recorded_at"] == consented.json()["decision_recorded_at"]
    assert changed.status_code == 409
    assert changed.json()["code"] == "consent_already_recorded"

    with invitation_session_factory() as session:
        invite = session.get(AssessmentInvite, UUID(created["id"]))
        assert invite is not None
        assert invite.token_hash != token
        assert token not in invite.token_hash
        assert invite.status is AssessmentInviteStatus.CONSENTED
        assert session.scalar(select(func.count()).select_from(CandidateConsent)) == 1
        consent = session.scalar(
            select(CandidateConsent).where(CandidateConsent.invite_id == invite.id)
        )
        assert consent is not None
        assert consent.notice_version == "pilot-v1"
        assert require_consented_invite(session, invite.id).id == invite.id
        events = list(session.scalars(select(AuditEvent).where(AuditEvent.entity_id == invite.id)))
        assert {event.event_type for event in events} == {
            "assessment_invite.created",
            "candidate_invite.accessed",
            "candidate_consent.recorded",
        }
        assert all(token not in str(event.metadata_json) for event in events)


@pytest.mark.anyio
async def test_decline_never_opens_assessment_and_revocation_is_immediate(
    invitation_client: AsyncClient,
    invitation_session_factory: sessionmaker[Session],
    delivery: RecordingDelivery,
    alpha_headers: dict[str, str],
) -> None:
    """A decline is persisted without penalty and a revoked link stops working."""

    created, token = await create_invite(invitation_client, alpha_headers, delivery)
    declined = await invitation_client.post(
        f"/v1/candidate/invites/{token}/consent", json={"decision": "decline"}
    )
    assert declined.status_code == 200
    assert declined.json()["status"] == "declined"
    assert declined.json()["can_start_assessment"] is False

    with invitation_session_factory() as session:
        with pytest.raises(AccessProblemError) as denied:
            require_consented_invite(session, UUID(created["id"]))
        assert denied.value.code == "candidate_consent_required"

    revoked = await invitation_client.post(
        f"/v1/roles/{ALPHA_ROLE_ID}/invites/{created['id']}/revoke",
        headers=alpha_headers,
    )
    repeated = await invitation_client.post(
        f"/v1/roles/{ALPHA_ROLE_ID}/invites/{created['id']}/revoke",
        headers=alpha_headers,
    )
    unavailable = await invitation_client.get(f"/v1/candidate/invites/{token}")
    assert revoked.status_code == repeated.status_code == 200
    assert revoked.json()["status"] == "revoked"
    assert revoked.json()["revoked_at"] is not None
    assert unavailable.status_code == 410
    assert unavailable.json()["code"] == "invitation_unavailable"


@pytest.mark.anyio
async def test_expired_pending_invalid_and_tampered_links_fail_safely(
    invitation_client: AsyncClient,
    invitation_session_factory: sessionmaker[Session],
    delivery: RecordingDelivery,
    alpha_headers: dict[str, str],
) -> None:
    """Every unusable token state fails without returning candidate or tenant data."""

    created, token = await create_invite(invitation_client, alpha_headers, delivery)
    with invitation_session_factory() as session:
        invite = session.get(AssessmentInvite, UUID(created["id"]))
        assert invite is not None
        invite.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        session.commit()

    expired = await invitation_client.get(f"/v1/candidate/invites/{token}")
    expired_again = await invitation_client.get(f"/v1/candidate/invites/{token}")
    assert expired.status_code == expired_again.status_code == 410
    assert expired.json()["code"] == "invitation_expired"
    with invitation_session_factory() as session:
        invite = session.get(AssessmentInvite, UUID(created["id"]))
        assert invite is not None
        assert invite.status is AssessmentInviteStatus.EXPIRED
        expiry_events = list(
            session.scalars(
                select(AuditEvent).where(
                    AuditEvent.entity_id == invite.id,
                    AuditEvent.event_type == "candidate_invite.expired",
                )
            )
        )
        assert len(expiry_events) == 1

        pending_token = InviteTokenCodec(INVITE_SECRET).generate()
        session.add(
            AssessmentInvite(
                role_profile_id=ALPHA_PROFILE_ID,
                email="pending@synthetic.example.invalid",
                token_hash=pending_token.token_hash,
                expires_at=datetime.now(UTC) + timedelta(hours=1),
                status=AssessmentInviteStatus.PENDING_DELIVERY,
            )
        )
        session.commit()

    pending = await invitation_client.get(f"/v1/candidate/invites/{pending_token.raw_token}")
    unknown = await invitation_client.get("/v1/candidate/invites/not-a-token")
    unknown_signed_token = InviteTokenCodec(INVITE_SECRET).generate().raw_token
    unknown_signed = await invitation_client.get(f"/v1/candidate/invites/{unknown_signed_token}")
    secret, signature = token.split(".")
    changed_first = "A" if signature[0] != "A" else "B"
    tampered = await invitation_client.get(
        f"/v1/candidate/invites/{secret}.{changed_first}{signature[1:]}"
    )
    assert (
        pending.status_code
        == unknown.status_code
        == unknown_signed.status_code
        == tampered.status_code
        == 404
    )
    assert pending.json()["code"] == unknown.json()["code"] == "resource_not_found"


@pytest.mark.anyio
async def test_internal_invite_rules_enforce_approval_tenant_role_and_expiry_policy(
    invitation_client: AsyncClient,
    invitation_session_factory: sessionmaker[Session],
    delivery: RecordingDelivery,
    alpha_headers: dict[str, str],
    beacon_headers: dict[str, str],
) -> None:
    """Internal endpoints reject drafts, archives, cross-tenant IDs, and unauthorized users."""

    unauthenticated = await invitation_client.post(
        f"/v1/roles/{ALPHA_ROLE_ID}/invites", json=invite_payload()
    )
    beacon_cross_tenant = await invitation_client.post(
        f"/v1/roles/{ALPHA_ROLE_ID}/invites",
        headers=beacon_headers,
        json=invite_payload(),
    )
    draft = await invitation_client.post(
        f"/v1/roles/{ALPHA_ROLE_ID}/invites",
        headers=alpha_headers,
        json=invite_payload(role_profile_id=str(DRAFT_PROFILE_ID)),
    )
    archived = await invitation_client.post(
        f"/v1/roles/{ARCHIVED_ROLE_ID}/invites",
        headers=alpha_headers,
        json=invite_payload(role_profile_id=str(ARCHIVED_PROFILE_ID)),
    )
    too_long = await invitation_client.post(
        f"/v1/roles/{ALPHA_ROLE_ID}/invites",
        headers=alpha_headers,
        json=invite_payload(expires_in_hours=49),
    )
    assert unauthenticated.status_code == 401
    assert beacon_cross_tenant.status_code == 404
    assert draft.status_code == 409
    assert draft.json()["code"] == "profile_not_approved"
    assert archived.status_code == 409
    assert archived.json()["code"] == "role_archived"
    assert too_long.status_code == 409
    assert too_long.json()["code"] == "invite_expiry_exceeds_policy"
    assert delivery.messages == []

    created, _ = await create_invite(invitation_client, alpha_headers, delivery)
    wrong_role = await invitation_client.post(
        f"/v1/roles/{BEACON_ROLE_ID}/invites/{created['id']}/revoke",
        headers=beacon_headers,
    )
    assert wrong_role.status_code == 404
    with invitation_session_factory() as session:
        invite = session.get(AssessmentInvite, UUID(created["id"]))
        assert invite is not None
        assert invite.status is AssessmentInviteStatus.ACTIVE


@pytest.mark.anyio
async def test_delivery_and_missing_security_configuration_fail_closed(
    invitation_session_factory: sessionmaker[Session],
    alpha_headers: dict[str, str],
) -> None:
    """No invite survives failed delivery, and absent signing secrets expose no links."""

    failing_app = build_app(invitation_session_factory, FailingDelivery())
    async with AsyncClient(
        transport=ASGITransport(app=failing_app), base_url="http://test"
    ) as client:
        failed = await client.post(
            f"/v1/roles/{ALPHA_ROLE_ID}/invites",
            headers=alpha_headers,
            json=invite_payload(),
        )
    assert failed.status_code == 502
    assert failed.json()["code"] == "invitation_delivery_failed"
    assert "provider" not in failed.json()["detail"]
    with invitation_session_factory() as session:
        assert session.scalar(select(func.count()).select_from(AssessmentInvite)) == 0

    unconfigured = InvitationSettings(token_signing_secret=None)
    missing_app = build_app(
        invitation_session_factory,
        RecordingDelivery(),
        settings=unconfigured,
    )
    async with AsyncClient(
        transport=ASGITransport(app=missing_app), base_url="http://test"
    ) as client:
        internal = await client.post(
            f"/v1/roles/{ALPHA_ROLE_ID}/invites",
            headers=alpha_headers,
            json=invite_payload(),
        )
        candidate = await client.get("/v1/candidate/invites/not-a-token")
    assert internal.status_code == candidate.status_code == 503
    assert internal.json()["code"] == "invitation_service_unavailable"


@pytest.mark.anyio
async def test_candidate_and_internal_rate_limits_return_retry_after(
    invitation_session_factory: sessionmaker[Session],
    delivery: RecordingDelivery,
    alpha_headers: dict[str, str],
) -> None:
    """Both anonymous bearer traffic and authenticated creation are throttled."""

    now = [10.0]
    limiter = InMemoryRateLimiter(clock=lambda: now[0])
    settings = invitation_settings(candidate_rate_limit=1, internal_rate_limit=1)
    app = build_app(invitation_session_factory, delivery, settings=settings, limiter=limiter)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created, token = await create_invite(client, alpha_headers, delivery)
        internal_limited = await client.post(
            f"/v1/roles/{ALPHA_ROLE_ID}/invites",
            headers=alpha_headers,
            json=invite_payload(email="second@synthetic.example.invalid"),
        )
        first_read = await client.get(f"/v1/candidate/invites/{token}")
        candidate_limited = await client.get(f"/v1/candidate/invites/{token}")
    assert created["status"] == "active"
    assert first_read.status_code == 200
    assert internal_limited.status_code == candidate_limited.status_code == 429
    assert internal_limited.headers["retry-after"] == "60"
    assert candidate_limited.json()["code"] == "rate_limit_exceeded"


def test_service_handles_disappeared_tenant_and_consent_gate_expiry(
    invitation_session_factory: sessionmaker[Session], delivery: RecordingDelivery
) -> None:
    """Defensive service branches fail closed under storage races and stale consent."""

    context = AuthorizationContext(
        user_id=ALPHA_USER_ID,
        organization=OrganizationScope(ALPHA_ORGANIZATION_ID),
        email="recruiter@alpha.example.invalid",
        name="Alpha Recruiter",
        role=InternalUserRole.RECRUITER,
    )
    settings = invitation_settings()
    with invitation_session_factory() as session:
        service = InternalInvitationService(
            session,
            context,
            settings,
            InviteTokenCodec(INVITE_SECRET),
            delivery,
        )
        # Simulate the tenant disappearing between authentication and service
        # work without violating database foreign keys.
        with (
            patch.object(session, "get", return_value=None),
            pytest.raises(AccessProblemError) as unavailable,
        ):
            service.create(
                ALPHA_ROLE_ID,
                InvitationCreateRequest(
                    role_profile_id=ALPHA_PROFILE_ID,
                    email="candidate@synthetic.example.invalid",
                ),
            )
        assert unavailable.value.code == "invitation_service_unavailable"

    with invitation_session_factory() as session:
        expired = AssessmentInvite(
            role_profile_id=ALPHA_PROFILE_ID,
            email="expired-consent@synthetic.example.invalid",
            token_hash="a" * 64,
            expires_at=datetime.now(UTC) - timedelta(seconds=1),
            status=AssessmentInviteStatus.CONSENTED,
        )
        session.add(expired)
        session.flush()
        session.add(
            CandidateConsent(
                invite_id=expired.id,
                decision=ConsentDecision.CONSENT,
                notice_version="pilot-v1",
            )
        )
        session.commit()
        with pytest.raises(AccessProblemError) as denied:
            require_consented_invite(session, expired.id)
        assert denied.value.code == "candidate_consent_required"


def test_seeded_repository_invite_lookup_is_tenant_scoped(
    invitation_session_factory: sessionmaker[Session],
) -> None:
    """Repository joins protect invitation IDs at the service data boundary."""

    from app.database.repositories import OrganizationDataAccess

    with invitation_session_factory() as session:
        invite = AssessmentInvite(
            role_profile_id=ALPHA_PROFILE_ID,
            email="lookup@synthetic.example.invalid",
            token_hash="b" * 64,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            status=AssessmentInviteStatus.ACTIVE,
        )
        session.add(invite)
        session.commit()
        alpha = OrganizationDataAccess(session, ALPHA_ORGANIZATION_ID)
        beacon = OrganizationDataAccess(session, BEACON_ORGANIZATION_ID)
        assert alpha.get_assessment_invite_for_role(ALPHA_ROLE_ID, invite.id) is invite
        assert alpha.get_assessment_invite_for_role(BEACON_ROLE_ID, invite.id) is None
        assert beacon.get_assessment_invite_for_role(ALPHA_ROLE_ID, invite.id) is None
