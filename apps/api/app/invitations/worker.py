"""Bounded local SMTP queue worker with committed claims and no uncertain retries."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, sessionmaker

from app.auth.config import AuthenticationSettings
from app.database.models import (
    AssessmentInvite,
    AssessmentInviteStatus,
    AuditEvent,
    InvitationDelivery,
    Organization,
    Role,
    RoleProfile,
)
from app.invitations.config import InvitationSettings
from app.invitations.credentials import CredentialContext
from app.invitations.delivery import build_invitation_email
from app.invitations.local_delivery import LocalSmtpInvitationDelivery
from app.invitations.queue import local_cipher, require_queue_database
from app.invitations.recovery import DeliveryDecision, DeliveryEvent, DeliveryState, decide_delivery

RECOVERY_GRACE = timedelta(minutes=2)


@dataclass(frozen=True, repr=False)
class _Claim:
    delivery_id: UUID
    invite_id: UUID
    context: CredentialContext
    ciphertext: bytes
    recipient: str
    organization_name: str
    invite_expires_at: datetime


def _apply(job: InvitationDelivery, decision: DeliveryDecision, now: datetime) -> None:
    job.state = decision.state
    job.updated_at = now
    if decision.delete_credential:
        job.credential_ciphertext = None
        job.credential_key_id = None
    if decision.increment_attempt:
        job.attempt_count += 1
        job.attempt_started_at = now


def _audit(session: Session, job: InvitationDelivery) -> None:
    """Attribute audit events to the owner resolved through the invite chain."""
    owner = session.scalar(
        select(Role.organization_id)
        .join(RoleProfile, RoleProfile.role_id == Role.id)
        .join(AssessmentInvite, AssessmentInvite.role_profile_id == RoleProfile.id)
        .where(AssessmentInvite.id == job.invite_id)
    )
    if owner is None:
        raise ValueError("delivery audit owner is unavailable")
    session.add(
        AuditEvent(
            organization_id=owner,
            actor_id=None,
            event_type=f"invitation_delivery.{job.state.value}",
            entity_type="assessment_invite",
            entity_id=job.invite_id,
            metadata_json={"attempt_count": job.attempt_count},
        )
    )


def _locked_job(session: Session, invite_id: UUID) -> InvitationDelivery | None:
    return session.scalar(
        select(InvitationDelivery)
        .where(InvitationDelivery.invite_id == invite_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def _eligible(invite: AssessmentInvite, now: datetime) -> bool:
    return invite.status is AssessmentInviteStatus.PENDING_DELIVERY and invite.expires_at > now


def cleanup_deliveries(
    factory: sessionmaker[Session], *, limit: int = 100, now: datetime | None = None
) -> int:
    """Purge expired/stale credentials without requiring encryption keys or SMTP.

    Rows are bounded and locked invite-first, matching revoke/privacy/completion.
    Only caller-owned disposable/local databases are authorized for this slice.
    """
    _limit(limit)
    instant = now or datetime.now(UTC)
    with factory() as session, session.begin():
        require_queue_database(session)
        invites = session.scalars(
            select(AssessmentInvite)
            .join(InvitationDelivery, InvitationDelivery.invite_id == AssessmentInvite.id)
            .where(
                InvitationDelivery.state.in_([DeliveryState.QUEUED, DeliveryState.SENDING]),
                or_(
                    InvitationDelivery.credential_expires_at <= instant,
                    (InvitationDelivery.state == DeliveryState.SENDING)
                    & (InvitationDelivery.attempt_started_at <= instant - RECOVERY_GRACE),
                    AssessmentInvite.status != AssessmentInviteStatus.PENDING_DELIVERY,
                    AssessmentInvite.expires_at <= instant,
                ),
            )
            .order_by(InvitationDelivery.credential_expires_at, AssessmentInvite.id)
            .limit(limit)
            .with_for_update(of=AssessmentInvite, skip_locked=True)
        ).all()
        changed = 0
        for invite in invites:
            job = _locked_job(session, invite.id)
            if job is None or job.state not in {DeliveryState.QUEUED, DeliveryState.SENDING}:
                continue
            decision = decide_delivery(
                state=job.state,
                event=DeliveryEvent.RECOVER,
                now=instant,
                credential_expires_at=job.credential_expires_at,
                invitation_eligible=_eligible(invite, instant),
                recovery_after=(
                    job.attempt_started_at + RECOVERY_GRACE if job.attempt_started_at else instant
                ),
            )
            _apply(job, decision, instant)
            _audit(session, job)
            changed += 1
        return changed


def _limit(limit: int) -> None:
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("delivery batch limit must be between 1 and 100")


class LocalDeliveryWorker:
    """Explicitly constructed local synthetic worker; never runs at app startup."""

    def __init__(
        self,
        factory: sessionmaker[Session],
        settings: InvitationSettings,
        authentication: AuthenticationSettings,
        adapter: LocalSmtpInvitationDelivery,
    ) -> None:
        if not isinstance(adapter, LocalSmtpInvitationDelivery):
            raise ValueError("local invitation worker requires local SMTP capture")
        self._cipher = local_cipher(settings, authentication)
        with factory() as session:
            require_queue_database(session)
        self._factory = factory
        self._settings = settings
        self._adapter = adapter

    def drain(self, *, limit: int = 25) -> int:
        """Run at most limit claims; SQL/audit failures propagate, never retry SMTP."""
        _limit(limit)
        cleanup_deliveries(self._factory, limit=limit)
        attempted = 0
        for _ in range(limit):
            claim = self._claim()
            if claim is None:
                break
            outcome = DeliveryEvent.UNKNOWN
            try:
                raw_token = self._cipher.decrypt(
                    claim.ciphertext, claim.context, now=datetime.now(UTC)
                )
                message = build_invitation_email(
                    recipient_email=claim.recipient,
                    organization_name=claim.organization_name,
                    invite_url=f"{self._settings.candidate_base_url}/{raw_token}",
                    expires_at=claim.invite_expires_at,
                    privacy_contact_email=self._settings.privacy_contact_email,
                )
                self._adapter.send(message)
                outcome = DeliveryEvent.ACCEPTED
            except Exception:
                pass
            self._complete(claim, outcome)
            attempted += 1
        return attempted

    def _claim(self) -> _Claim | None:
        """Return a send credential only after its claim transaction commits."""
        with self._factory() as session, session.begin():
            now = datetime.now(UTC)
            invite = session.scalar(
                select(AssessmentInvite)
                .join(InvitationDelivery, InvitationDelivery.invite_id == AssessmentInvite.id)
                .where(InvitationDelivery.state == DeliveryState.QUEUED)
                .order_by(InvitationDelivery.created_at, AssessmentInvite.id)
                .limit(1)
                .with_for_update(of=AssessmentInvite, skip_locked=True)
            )
            if invite is None:
                return None
            job = _locked_job(session, invite.id)
            assert job is not None
            owner = session.scalar(
                select(Role.organization_id)
                .join(RoleProfile, RoleProfile.role_id == Role.id)
                .where(RoleProfile.id == invite.role_profile_id)
            )
            eligible = _eligible(invite, now) and owner == job.organization_id
            decision = decide_delivery(
                state=job.state,
                event=DeliveryEvent.CLAIM,
                now=now,
                credential_expires_at=job.credential_expires_at,
                invitation_eligible=eligible,
            )
            _apply(job, decision, now)
            _audit(session, job)
            if not decision.increment_attempt:
                return None
            assert job.credential_ciphertext is not None and job.credential_key_id is not None
            organization = session.get(Organization, job.organization_id)
            assert organization is not None
            claim = _Claim(
                delivery_id=job.id,
                invite_id=invite.id,
                context=CredentialContext(
                    organization_id=job.organization_id,
                    invite_id=invite.id,
                    delivery_id=job.id,
                    expires_at=job.credential_expires_at,
                    key_id=job.credential_key_id,
                ),
                ciphertext=job.credential_ciphertext,
                recipient=invite.email,
                organization_name=organization.name,
                invite_expires_at=invite.expires_at,
            )
        return claim

    def _complete(self, claim: _Claim, outcome: DeliveryEvent) -> None:
        with self._factory() as session, session.begin():
            invite = session.scalar(
                select(AssessmentInvite)
                .where(AssessmentInvite.id == claim.invite_id)
                .with_for_update()
            )
            if invite is None:
                raise ValueError("delivery invitation is unavailable")
            job = _locked_job(session, invite.id)
            if job is None or job.id != claim.delivery_id:
                raise ValueError("delivery claim is unavailable")
            now = datetime.now(UTC)
            decision = decide_delivery(
                state=job.state,
                event=outcome,
                now=now,
                credential_expires_at=job.credential_expires_at,
                invitation_eligible=_eligible(invite, now),
            )
            was_sending = job.state is DeliveryState.SENDING
            _apply(job, decision, now)
            if was_sending and decision.state is DeliveryState.SENT:
                invite.status = AssessmentInviteStatus.ACTIVE
                invite.sent_at = now
            _audit(session, job)
