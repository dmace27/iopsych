"""Atomic issuance helpers for the explicitly local synthetic delivery queue."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from urllib.parse import urlsplit
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.config import AuthenticationSettings
from app.auth.errors import resource_conflict, resource_validation_failed, service_unavailable
from app.database.models import (
    AssessmentInvite,
    AssessmentInviteStatus,
    AuditEvent,
    InvitationDelivery,
    Role,
    RoleProfile,
)
from app.invitations.config import InvitationSettings
from app.invitations.credentials import CredentialContext, LocalCredentialCipher
from app.invitations.local_delivery import _SYNTHETIC_RECIPIENT
from app.invitations.recovery import DeliveryState
from app.invitations.schemas import InvitationCreateRequest

_IDEMPOTENCY_KEY = re.compile(r"[!-~]{16,128}", re.ASCII)


def require_queue_database(session: Session) -> None:
    """Queue locking and savepoint atomicity require PostgreSQL, never SQLite."""
    if session.get_bind().dialect.name != "postgresql":
        raise service_unavailable(
            code="local_queue_requires_postgresql", detail="Local delivery requires PostgreSQL."
        )


def local_cipher(
    settings: InvitationSettings, authentication: AuthenticationSettings
) -> LocalCredentialCipher:
    """Fail closed outside development, synthetic assignments and loopback UI."""
    if (
        not settings.local_queue_enabled
        or authentication.environment != "development"
        or not settings.allow_synthetic_definitions
        or settings.local_queue_key is None
        or settings.token_signing_secret is None
        or authentication.jwt_secret is None
        or urlsplit(settings.candidate_base_url).hostname not in {"localhost", "127.0.0.1", "::1"}
    ):
        raise ValueError("local invitation queue configuration is unavailable")
    return LocalCredentialCipher(
        key=settings.local_queue_key,
        key_id=settings.local_queue_key_id,
        forbidden_keys=(
            settings.token_signing_secret.get_secret_value(),
            authentication.jwt_secret.get_secret_value(),
        ),
    )


def issuance_digests(
    role_id: UUID, request: InvitationCreateRequest, idempotency_key: str | None
) -> tuple[str, str]:
    if idempotency_key is None or _IDEMPOTENCY_KEY.fullmatch(idempotency_key) is None:
        raise resource_validation_failed(
            code="invalid_idempotency_key", detail="A 16-128 character Idempotency-Key is required."
        )
    if _SYNTHETIC_RECIPIENT.fullmatch(request.email) is None:
        raise resource_validation_failed(
            code="synthetic_recipient_required",
            detail="Local delivery requires a synthetic address.",
        )
    canonical = {"role_id": str(role_id), "request": request.model_dump(mode="json")}
    return (
        sha256(idempotency_key.encode("ascii")).hexdigest(),
        sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
    )


def replay_invitation(
    session: Session, organization_id: UUID, role_id: UUID, digests: tuple[str, str]
) -> AssessmentInvite | None:
    job = session.scalar(
        select(InvitationDelivery).where(
            InvitationDelivery.organization_id == organization_id,
            InvitationDelivery.idempotency_digest == digests[0],
        )
    )
    if job is None:
        return None
    if job.request_digest != digests[1]:
        raise resource_conflict(
            code="idempotency_conflict", detail="The key was used for another request."
        )
    invite = session.scalar(
        select(AssessmentInvite)
        .join(RoleProfile, RoleProfile.id == AssessmentInvite.role_profile_id)
        .join(Role, Role.id == RoleProfile.role_id)
        .where(
            AssessmentInvite.id == job.invite_id,
            Role.id == role_id,
            Role.organization_id == organization_id,
        )
    )
    if invite is None:
        raise resource_conflict(
            code="delivery_integrity_failed", detail="The delivery is unavailable."
        )
    if (
        job.state in {DeliveryState.CANCELLED, DeliveryState.EXPIRED, DeliveryState.UNCERTAIN}
        or invite.status in {AssessmentInviteStatus.REVOKED, AssessmentInviteStatus.EXPIRED}
        or invite.expires_at <= datetime.now(UTC)
        or (
            job.state in {DeliveryState.QUEUED, DeliveryState.SENDING}
            and job.credential_expires_at <= datetime.now(UTC)
        )
    ):
        raise resource_conflict(
            code="invitation_reissue_required", detail="Revoke and reissue with a new key."
        )
    return invite


def require_resolved_prior_delivery(
    session: Session, organization_id: UUID, role_id: UUID, email: str
) -> None:
    """An uncertain attempt needs explicit revocation before replacement issuance."""
    unresolved = session.scalar(
        select(InvitationDelivery.id)
        .join(AssessmentInvite, AssessmentInvite.id == InvitationDelivery.invite_id)
        .join(RoleProfile, RoleProfile.id == AssessmentInvite.role_profile_id)
        .join(Role, Role.id == RoleProfile.role_id)
        .where(
            InvitationDelivery.organization_id == organization_id,
            Role.organization_id == organization_id,
            Role.id == role_id,
            AssessmentInvite.email == email,
            AssessmentInvite.status == AssessmentInviteStatus.PENDING_DELIVERY,
            InvitationDelivery.state.in_([DeliveryState.SENDING, DeliveryState.UNCERTAIN]),
        )
        .limit(1)
    )
    if unresolved is not None:
        raise resource_conflict(
            code="invitation_reissue_required",
            detail="Revoke the unresolved invitation before reissue.",
        )


def stage_delivery(
    session: Session,
    *,
    invite: AssessmentInvite,
    organization_id: UUID,
    actor_id: UUID,
    digests: tuple[str, str],
    raw_token: str,
    cipher: LocalCredentialCipher,
    key_id: str,
) -> None:
    """Bind queued credentials to the authoritative invite/profile tenant chain."""
    owner = session.scalar(
        select(Role.organization_id)
        .join(RoleProfile, RoleProfile.role_id == Role.id)
        .where(RoleProfile.id == invite.role_profile_id)
    )
    if owner != organization_id:
        raise ValueError("delivery tenant mismatch")
    now = datetime.now(UTC)
    delivery_id = uuid4()
    expiry = min(invite.expires_at, now + timedelta(minutes=15))
    context = CredentialContext(
        organization_id=organization_id,
        invite_id=invite.id,
        delivery_id=delivery_id,
        expires_at=expiry,
        key_id=key_id,
    )
    session.add(
        InvitationDelivery(
            id=delivery_id,
            organization_id=organization_id,
            invite_id=invite.id,
            idempotency_digest=digests[0],
            request_digest=digests[1],
            state=DeliveryState.QUEUED,
            credential_ciphertext=cipher.encrypt(raw_token, context),
            credential_key_id=key_id,
            credential_expires_at=expiry,
            updated_at=now,
            attempt_count=0,
        )
    )
    session.add(
        AuditEvent(
            organization_id=organization_id,
            actor_id=actor_id,
            event_type="invitation_delivery.queued",
            entity_type="assessment_invite",
            entity_id=invite.id,
            metadata_json={"mode": "local_synthetic"},
        )
    )
    session.flush()


def cancel_delivery(session: Session, invite_id: UUID) -> None:
    """Lock invite then delivery, matching worker order; caller owns audit/commit."""
    session.scalar(
        select(AssessmentInvite.id).where(AssessmentInvite.id == invite_id).with_for_update()
    )
    job = session.scalar(
        select(InvitationDelivery)
        .where(InvitationDelivery.invite_id == invite_id)
        .with_for_update()
    )
    if job is not None:
        if job.state in {DeliveryState.QUEUED, DeliveryState.SENDING}:
            job.state = DeliveryState.CANCELLED
        job.credential_ciphertext = None
        job.credential_key_id = None
        job.updated_at = datetime.now(UTC)
