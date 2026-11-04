"""Durable, bounded delivery worker; external sends happen only after issuance commits."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from cryptography.fernet import InvalidToken
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, sessionmaker

from app.database.models import (
    AssessmentInvite,
    AssessmentInviteStatus,
    AuditEvent,
    ProviderInvitationDelivery,
)
from app.database.models import (
    InvitationDeliveryStatus as DeliveryStatus,
)
from app.invitations.config import InvitationSettings
from app.invitations.delivery import InvitationDeliveryError, ProviderInvitationDeliveryAdapter
from app.invitations.encryption import decrypt_message, delivery_cipher

PENDING = (DeliveryStatus.QUEUED, DeliveryStatus.RETRYING)


def append_delivery_audit(
    session: Session, delivery: ProviderInvitationDelivery, event: str
) -> None:
    """Persist only opaque identifiers and safe operational state."""
    session.add(
        AuditEvent(
            organization_id=delivery.organization_id,
            actor_id=delivery.requested_by,
            event_type=f"invitation_delivery.{event}",
            entity_type="assessment_invite",
            entity_id=delivery.invite_id,
            metadata_json={
                "delivery_id": str(delivery.id),
                "status": delivery.status.value,
                "attempt_count": delivery.attempt_count,
            },
        )
    )


def cancel_delivery(session: Session, invite_id: UUID) -> None:
    """Erase pending credentials while the caller holds the invitation row lock."""
    delivery = session.scalar(
        select(ProviderInvitationDelivery)
        .where(ProviderInvitationDelivery.invite_id == invite_id)
        .with_for_update()
    )
    if delivery is not None and delivery.status in PENDING:
        delivery.encrypted_message = None
        delivery.status = DeliveryStatus.CANCELLED
        append_delivery_audit(session, delivery, "cancelled")


def stop_delivery(
    session: Session,
    delivery: ProviderInvitationDelivery,
    invite: AssessmentInvite,
    status: DeliveryStatus,
    code: str,
    now: datetime,
) -> None:
    """Stop ambiguous or permanent failures without ever generating a new email key."""
    delivery.status = status
    delivery.last_error_code = code
    delivery.encrypted_message = None
    if invite.status not in {AssessmentInviteStatus.REVOKED, AssessmentInviteStatus.EXPIRED}:
        invite.status = AssessmentInviteStatus.REVOKED
        invite.revoked_at = now
    append_delivery_audit(session, delivery, "stopped")


def process_delivery_batch(
    factory: sessionmaker[Session],
    settings: InvitationSettings,
    adapter: ProviderInvitationDeliveryAdapter,
    *,
    now: datetime | None = None,
) -> int:
    """Process committed rows once per batch, serializing each invitation before its outbox.

    A send/commit failure leaves the frozen ciphertext and provider key intact.
    Retry never extends the 23-hour deadline, shorter than Resend's 24-hour
    deduplication window. Multiple PostgreSQL workers skip busy invitations.
    """
    delivery_cipher(settings)  # Misconfigured workers fail before touching queued work.
    current = now or datetime.now(UTC)
    with factory() as session:
        rows = list(
            session.execute(
                select(ProviderInvitationDelivery.id, ProviderInvitationDelivery.invite_id)
                .where(
                    ProviderInvitationDelivery.status.in_(PENDING),
                    or_(
                        ProviderInvitationDelivery.next_attempt_at <= current,
                        ProviderInvitationDelivery.retry_until <= current,
                    ),
                )
                .order_by(ProviderInvitationDelivery.next_attempt_at, ProviderInvitationDelivery.id)
                .limit(settings.delivery_batch_size)
            )
        )
    processed = 0
    for delivery_id, invite_id in rows:
        # Each message has its own transaction, so a failure cannot roll back a
        # different delivery's outcome. Callers should retry after database errors.
        with factory.begin() as session:
            invite = session.scalar(
                select(AssessmentInvite)
                .where(AssessmentInvite.id == invite_id)
                .with_for_update(skip_locked=True)
            )
            if invite is None:
                continue
            delivery = session.scalar(
                select(ProviderInvitationDelivery)
                .where(ProviderInvitationDelivery.id == delivery_id)
                .with_for_update()
            )
            assert delivery is not None
            # Database waits must not extend the invite or safe retry lifetime.
            current = now or datetime.now(UTC)
            if delivery.status not in PENDING or (
                delivery.next_attempt_at > current and delivery.retry_until > current
            ):
                continue
            if invite.status is not AssessmentInviteStatus.ACTIVE:
                cancel_delivery(session, invite.id)
            elif invite.expires_at <= current or delivery.retry_until <= current:
                stop_delivery(
                    session,
                    delivery,
                    invite,
                    DeliveryStatus.REISSUE_REQUIRED,
                    "retry_window_closed",
                    current,
                )
            else:
                _attempt(session, settings, adapter, delivery, invite, current)
            processed += 1
    return processed


def _attempt(
    session: Session,
    settings: InvitationSettings,
    adapter: ProviderInvitationDeliveryAdapter,
    delivery: ProviderInvitationDelivery,
    invite: AssessmentInvite,
    now: datetime,
) -> None:
    """Send the exact original payload, retaining it only while a safe retry is possible."""
    assert delivery.encrypted_message is not None
    try:
        message = decrypt_message(delivery.encrypted_message, settings)
    except (InvalidToken, ValueError, TypeError, KeyError):
        stop_delivery(
            session, delivery, invite, DeliveryStatus.REISSUE_REQUIRED, "payload_unavailable", now
        )
        return
    delivery.attempt_count += 1
    try:
        provider_id = adapter.send(message, idempotency_key=f"invite/{delivery.id}")
    except InvitationDeliveryError as exc:
        if exc.permanent:
            stop_delivery(
                session, delivery, invite, DeliveryStatus.FAILED, "provider_rejected", now
            )
        else:
            delivery.status = DeliveryStatus.RETRYING
            delivery.last_error_code = "provider_outcome_uncertain"
            delay = min(60 * 2 ** min(delivery.attempt_count - 1, 6), 3600)
            delivery.next_attempt_at = now + timedelta(seconds=delay)
            append_delivery_audit(session, delivery, "retry_scheduled")
        return
    delivery.provider_message_id = provider_id
    delivery.status = DeliveryStatus.SENT
    delivery.last_error_code = None
    delivery.encrypted_message = None
    invite.sent_at = now
    append_delivery_audit(session, delivery, "sent")
