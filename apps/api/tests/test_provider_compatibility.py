"""Cross-mode contracts introduced by the reconciliation, using synthetic providers."""

from uuid import uuid4

import pytest
from httpx import AsyncClient
from pydantic import ValidationError
from sqlalchemy.orm import Session, sessionmaker

from app.database.seed import ALPHA_ROLE_ID
from app.invitations.encryption import decrypt_message
from app.invitations.queue import issuance_digests
from app.invitations.schemas import InvitationCreateRequest
from tests.test_invitation_delivery import queued
from tests.test_provider_invitations import (
    alpha_headers as alpha_headers,
)
from tests.test_provider_invitations import (
    anyio_backend as anyio_backend,
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
from tests.test_provider_invitations import (
    invitation_settings,
    invite_payload,
    token_from_message,
)


@pytest.mark.anyio
async def test_header_issuance_replays_and_rejects_conflicting_keys(
    invitation_client: AsyncClient, alpha_headers: dict[str, str]
) -> None:
    payload = invite_payload()
    payload.pop("request_id")
    headers = {**alpha_headers, "Idempotency-Key": "legacy-header-key-0001"}
    route = f"/v1/roles/{ALPHA_ROLE_ID}/invites"
    first = await invitation_client.post(route, json=payload, headers=headers)
    replay = await invitation_client.post(route, json=payload, headers=headers)
    assert first.status_code == replay.status_code == 201
    assert first.json()["id"] == replay.json()["id"]
    changed = await invitation_client.post(
        route, json={**payload, "expires_in_hours": 10}, headers=headers
    )
    assert changed.status_code == 409
    dual = await invitation_client.post(
        route, json={**payload, "request_id": str(uuid4())}, headers=headers
    )
    assert dual.status_code == 409


@pytest.mark.anyio
async def test_consent_purges_provider_payload_immediately(
    invitation_client: AsyncClient,
    alpha_headers: dict[str, str],
    invitation_session_factory: sessionmaker[Session],
) -> None:
    response = await invitation_client.post(
        f"/v1/roles/{ALPHA_ROLE_ID}/invites", json=invite_payload(), headers=alpha_headers
    )
    assert response.status_code == 201
    invite_id = response.json()["id"]
    item = queued(invitation_session_factory, invite_id)
    assert item.encrypted_message is not None
    token = token_from_message(decrypt_message(item.encrypted_message, invitation_settings()))
    consent = await invitation_client.post(
        f"/v1/candidate/invites/{token}/consent", json={"decision": "decline"}
    )
    assert consent.status_code == 200
    assert queued(invitation_session_factory, invite_id).encrypted_message is None


def test_local_digest_ignores_provider_key_and_modes_are_exclusive() -> None:
    payload = invite_payload()
    first = InvitationCreateRequest.model_validate(payload)
    second = first.model_copy(update={"request_id": None})
    assert issuance_digests(ALPHA_ROLE_ID, first, "local-key-00000001") == issuance_digests(
        ALPHA_ROLE_ID, second, "local-key-00000001"
    )
    with pytest.raises(ValidationError, match="separate delivery modes"):
        invitation_settings(local_queue_enabled=True)
