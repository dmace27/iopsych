"""Authenticated Resend events with durable deduplication and no retained body/PII."""

import json
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from pydantic import AwareDatetime, BaseModel, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from svix.webhooks import Webhook, WebhookVerificationError

from app.auth.dependencies import get_database_session
from app.auth.errors import AccessProblemError, service_unavailable
from app.database.models import (
    AssessmentInvite,
    InvitationDelivery,
    InvitationDeliveryEvent,
)
from app.database.models import (
    InvitationDeliveryStatus as DeliveryStatus,
)
from app.invitations.outbox import append_delivery_audit, stop_delivery

router = APIRouter(tags=["delivery webhooks"])
EVENT_STATUS = {
    "email.sent": DeliveryStatus.SENT,
    "email.delivered": DeliveryStatus.DELIVERED,
    "email.bounced": DeliveryStatus.BOUNCED,
    "email.complained": DeliveryStatus.COMPLAINED,
    "email.failed": DeliveryStatus.FAILED,
    "email.suppressed": DeliveryStatus.FAILED,
}
PRIORITY = {
    DeliveryStatus.QUEUED: 0,
    DeliveryStatus.RETRYING: 0,
    DeliveryStatus.SENT: 1,
    DeliveryStatus.DELIVERED: 2,
    DeliveryStatus.FAILED: 3,
    DeliveryStatus.BOUNCED: 4,
    DeliveryStatus.COMPLAINED: 5,
}


class EventData(BaseModel):
    """Select only the opaque email ID and optional opaque routing tag."""

    email_id: UUID
    tags: dict[str, str] = Field(default_factory=dict)


class DeliveryEvent(BaseModel):
    """Validate timestamps without retaining sender, recipient, subject or bounce details."""

    type: str = Field(max_length=80)
    created_at: AwareDatetime
    data: EventData


def invalid_webhook() -> AccessProblemError:
    """Avoid reflecting signed or unsigned provider payloads in API errors."""
    return AccessProblemError(
        status=400,
        code="invalid_delivery_webhook",
        title="Invalid webhook",
        detail="The delivery event could not be verified or accepted.",
    )


@router.post("/v1/webhooks/resend", status_code=204)
async def receive_delivery_event(
    request: Request, session: Annotated[Session, Depends(get_database_session)]
) -> Response:
    """Verify the original bytes and timestamp before parsing any event fields."""
    secret = request.app.state.invitation_settings.webhook_signing_secret
    if secret is None:
        raise service_unavailable(
            code="delivery_webhook_unconfigured", detail="Delivery webhooks are not configured."
        )
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 65_536:
            raise invalid_webhook()
    event_id = request.headers.get("svix-id", "")
    if not event_id or len(event_id) > 255:
        raise invalid_webhook()
    try:
        Webhook(secret.get_secret_value()).verify(bytes(body), dict(request.headers))
        payload = json.loads(body)
        if not isinstance(payload, dict):
            raise ValueError("invalid event")
        # Unsubscribed events from the same provider account have no side effects.
        if payload.get("type") not in {*EVENT_STATUS, "email.delivery_delayed"}:
            return Response(status_code=204)
        event = DeliveryEvent.model_validate(payload)
        await run_in_threadpool(_record_event, session, event_id, event)
    except (WebhookVerificationError, ValidationError, ValueError, TypeError):
        raise invalid_webhook() from None
    return Response(status_code=204)


def _record_event(session: Session, event_id: str, event: DeliveryEvent) -> None:
    """Lock invitation then delivery; a signed routing tag handles acceptance/commit races."""
    tag = event.data.tags.get("delivery_id")
    statement = select(InvitationDelivery.id, InvitationDelivery.invite_id)
    if tag is not None:
        statement = statement.where(InvitationDelivery.id == UUID(tag))
    else:
        statement = statement.where(
            InvitationDelivery.provider_message_id == str(event.data.email_id)
        )
    row = session.execute(statement).one_or_none()
    if row is None:
        return
    delivery_id, invite_id = row
    invite = session.scalar(
        select(AssessmentInvite).where(AssessmentInvite.id == invite_id).with_for_update()
    )
    assert invite is not None
    delivery = session.scalar(
        select(InvitationDelivery)
        .where(InvitationDelivery.id == delivery_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    assert delivery is not None
    if session.get(InvitationDeliveryEvent, event_id) is not None:
        return
    provider_id = str(event.data.email_id)
    if delivery.provider_message_id not in {None, provider_id}:
        raise ValueError("provider message mismatch")
    delivery.provider_message_id = provider_id
    session.add(
        InvitationDeliveryEvent(
            provider_event_id=event_id,
            delivery_id=delivery.id,
            event_type=event.type,
            occurred_at=event.created_at,
        )
    )
    status = EVENT_STATUS.get(event.type)
    if delivery.status in {DeliveryStatus.CANCELLED, DeliveryStatus.REISSUE_REQUIRED}:
        # Late messages may describe an already-replaced/revoked link. Never revive it.
        pass
    elif status is None:
        if delivery.status in {DeliveryStatus.QUEUED, DeliveryStatus.RETRYING, DeliveryStatus.SENT}:
            delivery.status = DeliveryStatus.SENT
            delivery.last_error_code = "delivery_delayed"
            delivery.encrypted_message = None
    elif PRIORITY[status] >= PRIORITY[delivery.status]:
        if status in {DeliveryStatus.FAILED, DeliveryStatus.BOUNCED, DeliveryStatus.COMPLAINED}:
            stop_delivery(
                session,
                delivery,
                invite,
                status,
                event.type.removeprefix("email."),
                datetime.now(UTC),
            )
        else:
            delivery.status = status
            delivery.last_error_code = None
            delivery.encrypted_message = None
            invite.sent_at = invite.sent_at or event.created_at
    append_delivery_audit(session, delivery, "webhook_recorded")
