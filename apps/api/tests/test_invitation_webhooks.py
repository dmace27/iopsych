"""Real Svix signatures, webhook replay, delivery races and safe event persistence."""

import base64
import json
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient, Response
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker
from svix.webhooks import Webhook

from app.database.models import (
    AssessmentInvite,
    AssessmentInviteStatus,
    InvitationDeliveryEvent,
)
from app.database.models import (
    InvitationDeliveryStatus as DeliveryStatus,
)
from app.database.seed import ALPHA_ROLE_ID
from app.invitations.encryption import decrypt_message
from app.invitations.outbox import process_delivery_batch
from tests.test_invitation_delivery import IdempotentProvider, enqueue, queued
from tests.test_invitations import (
    RecordingDelivery,
    build_app,
    invitation_settings,
    token_from_message,
)
from tests.test_invitations import (
    alpha_headers as alpha_headers,
)
from tests.test_invitations import (
    delivery as delivery,
)
from tests.test_invitations import (
    invitation_client as invitation_client,
)
from tests.test_invitations import (
    invitation_session_factory as invitation_session_factory,
)

WEBHOOK_SECRET = "whsec_" + base64.b64encode(b"w" * 32).decode()


@pytest.fixture
def anyio_backend() -> str:
    """Use asyncio for webhook HTTP tests."""
    return "asyncio"


@pytest.fixture
async def webhook_client(
    invitation_session_factory: sessionmaker[Session],
) -> AsyncGenerator[AsyncClient]:
    """Run the real webhook verifier against an isolated test database."""
    application = build_app(
        invitation_session_factory,
        RecordingDelivery(),
        settings=invitation_settings(webhook_signing_secret=SecretStr(WEBHOOK_SECRET)),
    )
    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        yield client


async def webhook(
    client: AsyncClient,
    delivery_id: UUID | None,
    provider_id: str,
    *,
    kind: str = "email.sent",
    event_id: str | None = None,
    age_seconds: int = 0,
    extra: dict[str, object] | None = None,
) -> int:
    """Sign the exact bytes; include PII in input to prove it is not retained."""
    payload: dict[str, object] = {
        "type": kind,
        "created_at": datetime.now(UTC).isoformat(),
        "data": {
            "email_id": provider_id,
            "tags": {"delivery_id": str(delivery_id)} if delivery_id else {},
            "from": "sender@example.invalid",
            "to": ["private-person@example.invalid"],
            "subject": "Private subject",
            "bounce": {"message": "Private provider reason"},
        },
    }
    if extra:
        payload.update(extra)
    return (
        await signed_request(
            client, json.dumps(payload), event_id=event_id, age_seconds=age_seconds
        )
    ).status_code


async def signed_request(
    client: AsyncClient, body: str, *, event_id: str | None = None, age_seconds: int = 0
) -> Response:
    """Use the provider's library to generate a timestamped signature."""
    timestamp = datetime.now(UTC) - timedelta(seconds=age_seconds)
    identifier = event_id or f"msg_{uuid4().hex}"
    response = await client.post(
        "/v1/webhooks/resend",
        content=body,
        headers={
            "svix-id": identifier,
            "svix-timestamp": str(int(timestamp.timestamp())),
            "svix-signature": Webhook(WEBHOOK_SECRET).sign(identifier, timestamp, body),
            "Content-Type": "application/json",
        },
    )
    return response


@pytest.mark.anyio
async def test_webhooks_accept_before_worker_commit_deduplicate_and_never_regress(
    invitation_client: AsyncClient,
    webhook_client: AsyncClient,
    invitation_session_factory: sessionmaker[Session],
    alpha_headers: dict[str, str],
) -> None:
    """An authenticated routing tag reconciles accepted mail before its response is durable."""
    created = await enqueue(invitation_client, alpha_headers)
    item = queued(invitation_session_factory, created["id"])
    provider_id = str(uuid4())
    event_id = f"msg_{uuid4().hex}"
    assert await webhook(webhook_client, item.id, provider_id, event_id=event_id) == 204
    assert await webhook(webhook_client, item.id, provider_id, event_id=event_id) == 204
    sent = queued(invitation_session_factory, created["id"])
    assert sent.status == DeliveryStatus.SENT and sent.encrypted_message is None
    assert (
        process_delivery_batch(
            invitation_session_factory, invitation_settings(), IdempotentProvider()
        )
        == 0
    )
    assert await webhook(webhook_client, None, provider_id, kind="email.delivered") == 204
    assert await webhook(webhook_client, item.id, provider_id, kind="email.sent") == 204
    assert await webhook(webhook_client, item.id, provider_id, kind="email.delivery_delayed") == 204
    assert queued(invitation_session_factory, created["id"]).status == DeliveryStatus.DELIVERED
    with invitation_session_factory() as session:
        events = list(session.scalars(select(InvitationDeliveryEvent)))
        assert len(events) == 4
        assert "private-person" not in str([value.__dict__ for value in events])
    mismatch = await webhook(webhook_client, item.id, str(uuid4()))
    assert mismatch == 400


@pytest.mark.anyio
@pytest.mark.parametrize(
    "kind,status",
    [
        ("email.bounced", DeliveryStatus.BOUNCED),
        ("email.complained", DeliveryStatus.COMPLAINED),
        ("email.failed", DeliveryStatus.FAILED),
        ("email.suppressed", DeliveryStatus.FAILED),
    ],
)
async def test_negative_events_stop_delivery_and_old_links(
    invitation_client: AsyncClient,
    webhook_client: AsyncClient,
    invitation_session_factory: sessionmaker[Session],
    alpha_headers: dict[str, str],
    kind: str,
    status: DeliveryStatus,
) -> None:
    """Hard failures are actionable, clear credentials and cannot be undone by late success."""
    created = await enqueue(invitation_client, alpha_headers)
    item = queued(invitation_session_factory, created["id"])
    assert item.encrypted_message
    token = token_from_message(decrypt_message(item.encrypted_message, invitation_settings()))
    provider_id = str(uuid4())
    assert await webhook(webhook_client, item.id, provider_id, kind=kind) == 204
    assert await webhook(webhook_client, item.id, provider_id, kind="email.delivered") == 204
    result = queued(invitation_session_factory, created["id"])
    assert result.status == status and result.encrypted_message is None
    assert (await invitation_client.get(f"/v1/candidate/invites/{token}")).status_code == 410
    with invitation_session_factory() as session:
        invite = session.get(AssessmentInvite, UUID(created["id"]))
        assert invite is not None and invite.status == AssessmentInviteStatus.REVOKED


@pytest.mark.anyio
async def test_delayed_and_late_cancelled_events_do_not_resend_or_reactivate(
    invitation_client: AsyncClient,
    webhook_client: AsyncClient,
    invitation_session_factory: sessionmaker[Session],
    alpha_headers: dict[str, str],
) -> None:
    """Resend owns downstream delivery delays; revoked links stay revoked after late events."""
    created = await enqueue(invitation_client, alpha_headers)
    item = queued(invitation_session_factory, created["id"])
    assert (
        await webhook(webhook_client, item.id, str(uuid4()), kind="email.delivery_delayed") == 204
    )
    delayed = queued(invitation_session_factory, created["id"])
    assert delayed.status == DeliveryStatus.SENT and delayed.last_error_code == "delivery_delayed"
    second = await enqueue(invitation_client, alpha_headers)
    cancelled = queued(invitation_session_factory, second["id"])
    await invitation_client.post(
        f"/v1/roles/{ALPHA_ROLE_ID}/invites/{second['id']}/revoke", headers=alpha_headers
    )
    assert await webhook(webhook_client, cancelled.id, str(uuid4()), kind="email.delivered") == 204
    assert queued(invitation_session_factory, second["id"]).status == DeliveryStatus.CANCELLED


@pytest.mark.anyio
async def test_webhook_verification_and_payload_limits_fail_closed(
    invitation_client: AsyncClient,
    webhook_client: AsyncClient,
    invitation_session_factory: sessionmaker[Session],
    alpha_headers: dict[str, str],
) -> None:
    """Reject fake, stale, oversized and malformed callbacks before any domain update."""
    assert (await invitation_client.post("/v1/webhooks/resend", content="{}")).status_code == 503
    assert (await webhook_client.post("/v1/webhooks/resend", content="{}")).status_code == 400
    assert (
        await webhook_client.post(
            "/v1/webhooks/resend", content="{}", headers={"svix-id": "x" * 256}
        )
    ).status_code == 400
    assert (
        await webhook_client.post("/v1/webhooks/resend", content="x" * 65537)
    ).status_code == 400
    assert (
        await webhook_client.post(
            "/v1/webhooks/resend",
            content="{}",
            headers={
                "svix-id": "fake",
                "svix-signature": "v1,invalid",
                "svix-timestamp": str(int(datetime.now(UTC).timestamp())),
            },
        )
    ).status_code == 400
    assert (await signed_request(webhook_client, "{}", age_seconds=600)).status_code == 400
    for body in ["not-json", "[]", '{"type":"email.sent"}']:
        assert (await signed_request(webhook_client, body)).status_code == 400
    assert await webhook(webhook_client, None, str(uuid4()), kind="unsubscribed.event") == 204
    assert await webhook(webhook_client, None, str(uuid4())) == 204
    assert await webhook(webhook_client, uuid4(), str(uuid4())) == 204
    created = await enqueue(invitation_client, alpha_headers)
    item = queued(invitation_session_factory, created["id"])
    assert (
        await webhook(
            webhook_client, item.id, str(uuid4()), extra={"created_at": "2026-11-03T12:00:00"}
        )
        == 400
    )
    with invitation_session_factory() as session:
        assert session.scalar(select(func.count()).select_from(InvitationDeliveryEvent)) == 0
    assert queued(invitation_session_factory, created["id"]).status == DeliveryStatus.QUEUED
