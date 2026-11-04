"""Durable issuance, provider retries, encrypted credentials and recovery regressions."""

import json
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from cryptography.fernet import Fernet, InvalidToken
from httpx import AsyncClient
from pydantic import SecretStr, ValidationError
from sqlalchemy import event, func, select
from sqlalchemy.exc import OperationalError
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
from app.database.seed import ALPHA_ROLE_ID, BEACON_ROLE_ID
from app.invitations.config import InvitationSettings
from app.invitations.delivery import (
    InvitationDeliveryError,
    InvitationEmail,
    UnconfiguredInvitationDelivery,
)
from app.invitations.encryption import decrypt_message, delivery_cipher, encrypt_message
from app.invitations.outbox import process_delivery_batch
from app.invitations.provider import ResendInvitationDelivery, build_invitation_delivery
from tests.test_provider_invitations import (
    RecordingDelivery,
    build_app,
    invitation_settings,
    invite_payload,
    token_from_message,
)
from tests.test_provider_invitations import (
    alpha_headers as alpha_headers,
)
from tests.test_provider_invitations import (
    beacon_headers as beacon_headers,
)
from tests.test_provider_invitations import (
    delivery as delivery,
)
from tests.test_provider_invitations import (
    invitation_client as invitation_client,
)
from tests.test_provider_invitations import (
    invitation_session_factory as invitation_session_factory,
)


@pytest.fixture
def anyio_backend() -> str:
    """Use asyncio for in-process API requests."""
    return "asyncio"


class IdempotentProvider:
    """Model provider deduplication, including acceptance followed by a lost response."""

    def __init__(self, *, timeout_once: bool = False, permanent: bool = False) -> None:
        self.requests: list[tuple[str, InvitationEmail]] = []
        self.accepted: dict[str, str] = {}
        self.timeout_once = timeout_once
        self.permanent = permanent

    def send(self, message: InvitationEmail, *, idempotency_key: str) -> str:
        """An identical provider key accepts at most one email in this test contract."""
        self.requests.append((idempotency_key, message))
        if self.permanent:
            raise InvitationDeliveryError("private provider detail", permanent=True)
        provider_id = self.accepted.setdefault(idempotency_key, str(uuid4()))
        if self.timeout_once:
            self.timeout_once = False
            raise InvitationDeliveryError("timeout after acceptance with private body")
        return provider_id


def queued(factory: sessionmaker[Session], invite_id: str) -> ProviderInvitationDelivery:
    """Return a detached snapshot, keeping test assertions out of worker transactions."""
    with factory() as session:
        item = session.scalar(
            select(ProviderInvitationDelivery).where(
                ProviderInvitationDelivery.invite_id == UUID(invite_id)
            )
        )
        assert item is not None
        session.expunge(item)
        return item


async def enqueue(
    client: AsyncClient, headers: dict[str, str], **overrides: object
) -> dict[str, Any]:
    """Create through the real request/audit transaction, without sending any mail."""
    response = await client.post(
        f"/v1/roles/{ALPHA_ROLE_ID}/invites", headers=headers, json=invite_payload(**overrides)
    )
    assert response.status_code == 201, response.text
    result: dict[str, Any] = response.json()
    assert result["sent_at"] is None
    return result


@pytest.mark.anyio
async def test_issuance_is_idempotent_and_stores_only_encrypted_payload(
    invitation_client: AsyncClient,
    invitation_session_factory: sessionmaker[Session],
    alpha_headers: dict[str, str],
    delivery: RecordingDelivery,
) -> None:
    """Repeated clicks cannot create another token, job or email, even after sending."""
    request_id = str(uuid4())
    first = await enqueue(invitation_client, alpha_headers, request_id=request_id)
    repeated = await enqueue(invitation_client, alpha_headers, request_id=request_id)
    assert first == repeated
    assert delivery.messages == []
    item = queued(invitation_session_factory, first["id"])
    assert item.status == DeliveryStatus.QUEUED and item.encrypted_message
    message = decrypt_message(item.encrypted_message, invitation_settings())
    token = token_from_message(message)
    assert token not in item.encrypted_message
    assert first["email"] not in item.encrypted_message
    assert "token" not in first and "encrypted_message" not in first
    conflict = await invitation_client.post(
        f"/v1/roles/{ALPHA_ROLE_ID}/invites",
        headers=alpha_headers,
        json=invite_payload(request_id=request_id, email="different@example.invalid"),
    )
    assert conflict.status_code == 409 and conflict.json()["code"] == "invitation_request_conflict"
    provider = IdempotentProvider()
    assert process_delivery_batch(invitation_session_factory, invitation_settings(), provider) == 1
    sent = queued(invitation_session_factory, first["id"])
    assert sent.status == DeliveryStatus.SENT and sent.encrypted_message is None
    assert process_delivery_batch(invitation_session_factory, invitation_settings(), provider) == 0
    again = await invitation_client.post(
        f"/v1/roles/{ALPHA_ROLE_ID}/invites",
        headers=alpha_headers,
        json=invite_payload(request_id=request_id),
    )
    assert again.json()["id"] == first["id"] and again.json()["sent_at"]
    with invitation_session_factory() as session:
        assert session.scalar(select(func.count()).select_from(ProviderInvitationDelivery)) == 1
        events = list(session.scalars(select(AuditEvent)))
        assert token not in str([value.metadata_json for value in events])
        assert (
            len([value for value in events if value.event_type == "invitation_delivery.queued"])
            == 1
        )
    progress = await invitation_client.get(
        f"/v1/roles/{ALPHA_ROLE_ID}/invites/{first['id']}/delivery", headers=alpha_headers
    )
    assert progress.status_code == 200 and progress.json()["status"] == "sent"
    assert "encrypted_message" not in progress.json()


@pytest.mark.anyio
async def test_request_audit_failure_never_sends_or_leaves_queued_credentials(
    invitation_client: AsyncClient,
    invitation_session_factory: sessionmaker[Session],
    alpha_headers: dict[str, str],
    delivery: RecordingDelivery,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The worker cannot observe a rolled-back invitation/outbox/issuance audit."""

    def fail_commit(session: Session) -> None:
        raise OperationalError("commit", {}, Exception("private database failure"))

    monkeypatch.setattr(Session, "commit", fail_commit)
    response = await invitation_client.post(
        f"/v1/roles/{ALPHA_ROLE_ID}/invites", headers=alpha_headers, json=invite_payload()
    )
    assert response.status_code == 500 and response.json()["code"] == "audit_persistence_failed"
    assert delivery.messages == []
    with invitation_session_factory() as session:
        assert session.scalar(select(func.count()).select_from(AssessmentInvite)) == 0
        assert session.scalar(select(func.count()).select_from(ProviderInvitationDelivery)) == 0
    assert (
        process_delivery_batch(
            invitation_session_factory, invitation_settings(), IdempotentProvider()
        )
        == 0
    )


@pytest.mark.anyio
async def test_acceptance_then_worker_commit_failure_retries_exact_original_email(
    invitation_client: AsyncClient,
    invitation_session_factory: sessionmaker[Session],
    alpha_headers: dict[str, str],
) -> None:
    """A delivered link already exists durably; a crash retries the same provider key/payload."""
    created = await enqueue(invitation_client, alpha_headers)
    provider = IdempotentProvider()

    def fail_commit(session: Session) -> None:
        raise OperationalError("commit", {}, Exception("database unavailable after acceptance"))

    event.listen(Session, "before_commit", fail_commit)
    try:
        with pytest.raises(OperationalError):
            process_delivery_batch(invitation_session_factory, invitation_settings(), provider)
    finally:
        event.remove(Session, "before_commit", fail_commit)
    assert queued(invitation_session_factory, created["id"]).status == DeliveryStatus.QUEUED
    token = token_from_message(provider.requests[0][1])
    assert (await invitation_client.get(f"/v1/candidate/invites/{token}")).status_code == 200
    changed_settings = invitation_settings(
        delivery_from_email="changed@example.invalid",
        privacy_contact_email="changed-privacy@example.invalid",
    )
    process_delivery_batch(invitation_session_factory, changed_settings, provider)
    assert len(provider.requests) == 2 and len(provider.accepted) == 1
    assert provider.requests[0] == provider.requests[1]
    assert queued(invitation_session_factory, created["id"]).encrypted_message is None


@pytest.mark.anyio
async def test_timeout_after_acceptance_uses_bounded_backoff_and_same_key(
    invitation_client: AsyncClient,
    invitation_session_factory: sessionmaker[Session],
    alpha_headers: dict[str, str],
) -> None:
    """A timeout is an uncertain outcome, never a reason to mint another invitation."""
    created = await enqueue(invitation_client, alpha_headers)
    provider = IdempotentProvider(timeout_once=True)
    process_delivery_batch(invitation_session_factory, invitation_settings(), provider)
    retry = queued(invitation_session_factory, created["id"])
    assert retry.status == DeliveryStatus.RETRYING and retry.encrypted_message
    assert retry.last_error_code == "provider_outcome_uncertain"
    assert process_delivery_batch(invitation_session_factory, invitation_settings(), provider) == 0
    assert (
        process_delivery_batch(
            invitation_session_factory, invitation_settings(), provider, now=retry.next_attempt_at
        )
        == 1
    )
    assert len(provider.accepted) == 1 and provider.requests[0] == provider.requests[1]


@pytest.mark.anyio
@pytest.mark.parametrize("failure", ["permanent", "deadline", "expiry", "corrupt"])
async def test_terminal_delivery_failures_erase_credentials_and_revoke_old_link(
    invitation_client: AsyncClient,
    invitation_session_factory: sessionmaker[Session],
    alpha_headers: dict[str, str],
    failure: str,
) -> None:
    """An unsafe retry is replaced only by a new explicit, separately audited issuance."""
    created = await enqueue(invitation_client, alpha_headers)
    snapshot = queued(invitation_session_factory, created["id"])
    assert snapshot.encrypted_message
    token = token_from_message(decrypt_message(snapshot.encrypted_message, invitation_settings()))
    with invitation_session_factory.begin() as session:
        item = session.get(ProviderInvitationDelivery, snapshot.id)
        invite = session.get(AssessmentInvite, UUID(created["id"]))
        assert item and invite
        if failure == "deadline":
            item.retry_until = datetime.now(UTC) - timedelta(seconds=1)
        if failure == "expiry":
            invite.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        if failure == "corrupt":
            item.encrypted_message = "invalid-authenticated-ciphertext"
    provider = IdempotentProvider(permanent=failure == "permanent")
    process_delivery_batch(invitation_session_factory, invitation_settings(), provider)
    result = queued(invitation_session_factory, created["id"])
    assert result.status == (
        DeliveryStatus.FAILED if failure == "permanent" else DeliveryStatus.REISSUE_REQUIRED
    )
    assert result.encrypted_message is None
    assert len(provider.requests) == (1 if failure == "permanent" else 0)
    assert (await invitation_client.get(f"/v1/candidate/invites/{token}")).status_code == 410


@pytest.mark.anyio
async def test_revocation_reissue_and_tenant_safe_progress(
    invitation_client: AsyncClient,
    invitation_session_factory: sessionmaker[Session],
    alpha_headers: dict[str, str],
    beacon_headers: dict[str, str],
) -> None:
    """Replacing a link is explicit, idempotent and makes the previous link unavailable."""
    created = await enqueue(invitation_client, alpha_headers)
    previous = queued(invitation_session_factory, created["id"])
    assert previous.encrypted_message
    token = token_from_message(decrypt_message(previous.encrypted_message, invitation_settings()))
    path = f"/v1/roles/{ALPHA_ROLE_ID}/invites/{created['id']}"
    replacement = {"request_id": str(uuid4())}
    for method, suffix, body in [
        ("GET", "/delivery", None),
        ("POST", "/reissue", replacement),
        ("POST", "/revoke", None),
    ]:
        response = await invitation_client.request(
            method, path + suffix, json=body, headers=beacon_headers
        )
        assert response.status_code == 404
    new = await invitation_client.post(path + "/reissue", json=replacement, headers=alpha_headers)
    repeated = await invitation_client.post(
        path + "/reissue", json=replacement, headers=alpha_headers
    )
    assert new.status_code == repeated.status_code == 201
    assert new.json()["id"] == repeated.json()["id"] != created["id"]
    assert queued(invitation_session_factory, created["id"]).status == DeliveryStatus.CANCELLED
    assert queued(invitation_session_factory, created["id"]).encrypted_message is None
    assert (await invitation_client.get(f"/v1/candidate/invites/{token}")).status_code == 410
    provider = IdempotentProvider()
    process_delivery_batch(invitation_session_factory, invitation_settings(), provider)
    assert len(provider.accepted) == 1
    new_token = token_from_message(provider.requests[0][1])
    await invitation_client.post(
        f"/v1/candidate/invites/{new_token}/consent", json={"decision": "decline"}
    )
    denied = await invitation_client.post(
        f"/v1/roles/{ALPHA_ROLE_ID}/invites/{new.json()['id']}/reissue",
        json={"request_id": str(uuid4())},
        headers=alpha_headers,
    )
    assert denied.status_code == 409 and denied.json()["code"] == "invitation_already_used"
    unknown = await invitation_client.get(
        f"/v1/roles/{BEACON_ROLE_ID}/invites/{created['id']}/delivery", headers=beacon_headers
    )
    assert unknown.status_code == 404
    cancelled = await enqueue(invitation_client, alpha_headers)
    cancelled_path = f"/v1/roles/{ALPHA_ROLE_ID}/invites/{cancelled['id']}/revoke"
    assert (await invitation_client.post(cancelled_path, headers=alpha_headers)).status_code == 200
    assert (await invitation_client.post(cancelled_path, headers=alpha_headers)).status_code == 200
    assert process_delivery_batch(invitation_session_factory, invitation_settings(), provider) == 0


def test_encryption_rotation_configuration_and_adapter_selection() -> None:
    """Keys are independent, payloads authenticate, and only configured providers can send."""
    settings = invitation_settings()
    message = InvitationEmail(
        "recipient@example.invalid",
        "Subject",
        "secure-link",
        "<p>secure-link</p>",
        "sender@example.invalid",
    )
    ciphertext = encrypt_message(message, settings)
    rotated = invitation_settings(
        delivery_encryption_key=Fernet.generate_key().decode(),
        delivery_previous_encryption_key=settings.delivery_encryption_key,
    )
    assert decrypt_message(ciphertext, rotated) == message
    with pytest.raises(InvalidToken):
        decrypt_message(
            ciphertext, invitation_settings(delivery_encryption_key=Fernet.generate_key().decode())
        )
    with pytest.raises(ValueError, match="not configured"):
        delivery_cipher(InvitationSettings())
    with pytest.raises(ValidationError):
        invitation_settings(delivery_encryption_key="short")
    with pytest.raises(ValidationError):
        invitation_settings(delivery_from_email="bad\naddress")
    assert isinstance(build_invitation_delivery(settings), UnconfiguredInvitationDelivery)
    assert invitation_settings(delivery_api_key=SecretStr("   ")).delivery_api_key is None
    assert (
        invitation_settings(webhook_signing_secret=SecretStr("  ")).webhook_signing_secret is None
    )
    assert invitation_settings(
        webhook_signing_secret=SecretStr(" secret ")
    ).webhook_signing_secret == SecretStr("secret")
    configured = invitation_settings(
        delivery_provider="resend", delivery_api_key=SecretStr("test-only-key")
    )
    assert isinstance(build_invitation_delivery(configured), ResendInvitationDelivery)
    assert isinstance(
        build_invitation_delivery(invitation_settings(delivery_provider="resend")),
        UnconfiguredInvitationDelivery,
    )


@pytest.mark.parametrize(
    "failure", [400, 408, 409, 422, 429, 500, "timeout", "url", "json", "missing", "invalid-id"]
)
def test_resend_adapter_safe_error_contract(failure: int | str) -> None:
    """Do not leak responses/credentials, and distinguish permanent rejections from uncertainty."""
    from email.message import Message
    from io import BytesIO
    from unittest.mock import MagicMock
    from urllib.error import HTTPError, URLError

    message = InvitationEmail(
        "person@example.invalid",
        "Subject",
        "raw-secret-link",
        "<p>raw-secret-link</p>",
        "sender@example.invalid",
    )
    adapter = ResendInvitationDelivery(SecretStr("test-private-api-key"), timeout=5)
    response = MagicMock()
    body = {"json": b"not-json", "missing": b"{}", "invalid-id": b'{"id":"invalid"}'}.get(
        str(failure), b"{}"
    )
    response.__enter__.return_value.read.return_value = body
    error: Exception | None = None
    if isinstance(failure, int):
        error = HTTPError(
            "https://api.resend.com/emails",
            failure,
            "private body",
            Message(),
            BytesIO(b"private body"),
        )
    if failure == "timeout":
        error = TimeoutError("private timeout body")
    if failure == "url":
        error = URLError("private network body")
    with (
        patch("app.invitations.provider.urlopen", side_effect=error, return_value=response),
        pytest.raises(InvitationDeliveryError) as caught,
    ):
        adapter.send(message, idempotency_key="invite/test")
    assert caught.value.permanent == (
        isinstance(failure, int) and 400 <= failure < 500 and failure not in {408, 409, 429}
    )
    assert "private" not in str(caught.value) and "raw-secret-link" not in str(caught.value)


def test_resend_adapter_sends_documented_payload_with_stable_key() -> None:
    """The wire request is bounded, HTTPS-only and includes an opaque webhook routing tag."""
    from unittest.mock import MagicMock

    message = InvitationEmail(
        "person@example.invalid", "Subject", "text", "<p>html</p>", "sender@example.invalid"
    )
    provider_id = str(uuid4())
    response = MagicMock()
    response.__enter__.return_value.read.return_value = json.dumps({"id": provider_id}).encode()
    with patch("app.invitations.provider.urlopen", return_value=response) as send:
        result = ResendInvitationDelivery(SecretStr("api-key"), timeout=5).send(
            message, idempotency_key="invite/test-id"
        )
    assert result == provider_id
    request = send.call_args.args[0]
    assert request.full_url == "https://api.resend.com/emails"
    assert request.get_header("Idempotency-key") == "invite/test-id"
    assert send.call_args.kwargs["timeout"] == 5
    assert json.loads(request.data) == {
        "from": "sender@example.invalid",
        "to": ["person@example.invalid"],
        "subject": "Subject",
        "text": "text",
        "html": "<p>html</p>",
        "tags": [{"name": "delivery_id", "value": "test-id"}],
    }


@pytest.mark.anyio
@pytest.mark.parametrize("missing", ["encryption", "provider"])
async def test_unconfigured_issuance_fails_before_creating_any_queue(
    invitation_session_factory: sessionmaker[Session],
    alpha_headers: dict[str, str],
    missing: str,
) -> None:
    """A missing encryption key or sending adapter produces actionable configuration feedback."""
    from httpx import ASGITransport

    settings = (
        invitation_settings(delivery_encryption_key=None)
        if missing == "encryption"
        else invitation_settings()
    )
    app = build_app(
        invitation_session_factory,
        None if missing == "provider" else RecordingDelivery(),
        settings=settings,
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            f"/v1/roles/{ALPHA_ROLE_ID}/invites", headers=alpha_headers, json=invite_payload()
        )
        assert response.status_code == 503
        assert response.json()["code"] == "invitation_delivery_unconfigured"
    with invitation_session_factory() as session:
        assert session.scalar(select(func.count()).select_from(ProviderInvitationDelivery)) == 0


@pytest.mark.anyio
async def test_legacy_invitation_has_no_invented_delivery_state(
    invitation_client: AsyncClient,
    invitation_session_factory: sessionmaker[Session],
    alpha_headers: dict[str, str],
) -> None:
    """Migration preserves legacy invites; absence of delivery history is explicit."""
    from app.database.seed import ALPHA_PROFILE_ID

    with invitation_session_factory.begin() as session:
        invite = AssessmentInvite(
            role_profile_id=ALPHA_PROFILE_ID,
            email="legacy@example.invalid",
            token_hash="f" * 64,
            status=AssessmentInviteStatus.ACTIVE,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        session.add(invite)
        session.flush()
        invite_id = invite.id
    response = await invitation_client.get(
        f"/v1/roles/{ALPHA_ROLE_ID}/invites/{invite_id}/delivery", headers=alpha_headers
    )
    assert response.status_code == 404


@pytest.mark.anyio
@pytest.mark.parametrize("change", ["cancel", "reschedule", "consent"])
async def test_worker_rechecks_state_after_selecting_a_batch(
    invitation_client: AsyncClient,
    invitation_session_factory: sessionmaker[Session],
    alpha_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
    change: str,
) -> None:
    """Another worker, revocation or candidate decision can win before a selected row is locked."""
    created = await enqueue(invitation_client, alpha_headers)
    snapshot = queued(invitation_session_factory, created["id"])
    original_close = Session.close
    pending = True

    def close_and_change(session: Session) -> None:
        nonlocal pending
        original_close(session)
        if not pending:
            return
        pending = False
        with invitation_session_factory.begin() as concurrent:
            item = concurrent.get(ProviderInvitationDelivery, snapshot.id)
            invite = concurrent.get(AssessmentInvite, UUID(created["id"]))
            assert item and invite
            if change == "cancel":
                item.status = DeliveryStatus.CANCELLED
                item.encrypted_message = None
            elif change == "reschedule":
                item.status = DeliveryStatus.RETRYING
                item.next_attempt_at = datetime.now(UTC) + timedelta(hours=1)
            else:
                invite.status = AssessmentInviteStatus.CONSENTED

    monkeypatch.setattr(Session, "close", close_and_change)
    provider = IdempotentProvider()
    count = process_delivery_batch(invitation_session_factory, invitation_settings(), provider)
    assert count == (1 if change == "consent" else 0)
    assert provider.requests == []
    if change == "consent":
        assert queued(invitation_session_factory, created["id"]).encrypted_message is None


def test_worker_cli_reports_counts_and_safe_failures(
    invitation_session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The scheduler command is runnable and never dumps database/provider exceptions."""
    from app.invitations import provider_worker as worker

    engine = invitation_session_factory.kw["bind"]
    monkeypatch.setattr(worker, "InvitationSettings", invitation_settings)
    monkeypatch.setattr(worker, "create_database_engine", lambda: engine)
    monkeypatch.setattr(worker, "create_session_factory", lambda value: invitation_session_factory)
    monkeypatch.setattr(worker, "build_invitation_delivery", lambda settings: IdempotentProvider())
    worker.main()
    assert "0 processed" in capsys.readouterr().out
    monkeypatch.setattr(
        worker, "build_invitation_delivery", lambda settings: UnconfiguredInvitationDelivery()
    )
    with pytest.raises(SystemExit, match="not configured"):
        worker.main()
    monkeypatch.setattr(worker, "build_invitation_delivery", lambda settings: IdempotentProvider())

    def fail(*args: object, **kwargs: object) -> int:
        raise OperationalError("private SQL", {}, Exception("private secret"))

    monkeypatch.setattr(worker, "process_delivery_batch", fail)
    with pytest.raises(SystemExit, match="Delivery batch failed") as caught:
        worker.main()
    assert "private" not in str(caught.value)


def test_provider_credential_change_cannot_retry_in_another_scope() -> None:
    """Changing provider accounts/keys must not bypass provider deduplication on pending mail."""
    settings = invitation_settings(delivery_api_key=SecretStr("original-provider-key"))
    message = InvitationEmail("person@example.invalid", "subject", "secure-token", "html")
    ciphertext = encrypt_message(message, settings)
    with pytest.raises(ValueError, match="scope changed"):
        decrypt_message(
            ciphertext, invitation_settings(delivery_api_key=SecretStr("different-provider-key"))
        )
