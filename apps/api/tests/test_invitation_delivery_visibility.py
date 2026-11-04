"""Read-only delivery visibility using synthetic rows in isolated SQLite."""

from __future__ import annotations

# ruff: noqa: F811 -- pytest fixture parameters intentionally shadow imports.
from typing import Any
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import Engine, event, select
from sqlalchemy.orm import Session, sessionmaker

from app.auth.context import AuthorizationContext, OrganizationScope
from app.database.models import AssessmentInvite, InternalUserRole, InvitationDelivery
from app.database.seed import (
    ALPHA_ORGANIZATION_ID,
    ALPHA_PROFILE_ID,
    ALPHA_USER_ID,
    BEACON_ORGANIZATION_ID,
    BEACON_PROFILE_ID,
    BEACON_ROLE_ID,
)
from app.invitations.discovery import invitation_responses
from app.invitations.recovery import DeliveryState
from app.invitations.service import InternalInvitationService
from tests.test_invitation_discovery import NOW, PATH, seed_invites
from tests.test_invitations import (  # noqa: F401
    alpha_headers,
    anyio_backend,
    beacon_headers,
    delivery,
    invitation_client,
    invitation_session_factory,
)


def add_delivery(
    session: Session,
    identifier: str,
    state: DeliveryState,
    organization_id: UUID = ALPHA_ORGANIZATION_ID,
) -> None:
    pending = state in {DeliveryState.QUEUED, DeliveryState.SENDING}
    session.add(
        InvitationDelivery(
            invite_id=UUID(identifier),
            organization_id=organization_id,
            idempotency_digest=f"{UUID(identifier).int:064x}",
            request_digest="e" * 64,
            state=state,
            credential_ciphertext=b"synthetic-private-ciphertext" if pending else None,
            credential_key_id="synthetic-private-key" if pending else None,
            credential_expires_at=NOW,
            updated_at=NOW,
        )
    )


@pytest.mark.anyio
async def test_all_states_and_legacy_null_in_one_safe_page(
    invitation_client: AsyncClient,
    invitation_session_factory: sessionmaker[Session],
    alpha_headers: dict[str, str],
) -> None:
    identifiers = seed_invites(invitation_session_factory, 7)
    expected = dict(zip(identifiers, [*DeliveryState, None], strict=True))
    with invitation_session_factory() as session:
        original_status = {
            str(invite.id): invite.status.value
            for invite in session.scalars(select(AssessmentInvite))
        }
        for identifier, state in expected.items():
            if state is not None:
                add_delivery(session, identifier, state)
        session.commit()
    response = await invitation_client.get(PATH, headers=alpha_headers)
    assert response.status_code == 200
    for item in response.json()["items"]:
        assert item["delivery_state"] == expected[item["id"]]
        assert item["status"] == original_status[item["id"]]
        assert set(item) == {
            "id",
            "role_profile_id",
            "email",
            "expires_at",
            "status",
            "sent_at",
            "revoked_at",
            "created_at",
            "delivery_state",
        }
    assert "synthetic-private" not in response.text


@pytest.mark.anyio
@pytest.mark.parametrize("limit", [1, 100])
async def test_one_bounded_projection_query_per_page(
    invitation_client: AsyncClient,
    invitation_session_factory: sessionmaker[Session],
    database_engine: Engine,
    alpha_headers: dict[str, str],
    limit: int,
) -> None:
    identifiers = seed_invites(invitation_session_factory, 101)
    with invitation_session_factory() as session:
        for identifier in identifiers:
            add_delivery(session, identifier, DeliveryState.SENT)
        session.commit()
    queries: list[tuple[str, Any]] = []

    def capture(
        conn: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        if statement.lstrip().startswith("SELECT") and "invitation_deliveries" in statement:
            queries.append((statement, parameters))

    event.listen(database_engine, "before_cursor_execute", capture)
    try:
        response = await invitation_client.get(PATH, headers=alpha_headers, params={"limit": limit})
    finally:
        event.remove(database_engine, "before_cursor_execute", capture)
    assert response.status_code == 200
    assert len(response.json()["items"]) == limit
    assert len(queries) == 1
    statement, parameters = queries[0]
    assert len(parameters) == limit + 2  # Page IDs and both tenant predicates.
    assert "credential" not in statement and "digest" not in statement
    assert all(item["delivery_state"] == "sent" for item in response.json()["items"])


@pytest.mark.anyio
async def test_corrupt_queue_tenants_and_foreign_invites_cannot_expose_state(
    invitation_client: AsyncClient,
    invitation_session_factory: sessionmaker[Session],
    alpha_headers: dict[str, str],
    beacon_headers: dict[str, str],
) -> None:
    local = seed_invites(invitation_session_factory, 1)[0]
    foreign = seed_invites(invitation_session_factory, 1, BEACON_PROFILE_ID, offset=10)[0]
    with invitation_session_factory() as session:
        add_delivery(session, local, DeliveryState.UNCERTAIN, BEACON_ORGANIZATION_ID)
        add_delivery(session, foreign, DeliveryState.SENT, ALPHA_ORGANIZATION_ID)
        session.commit()
        # Even a foreign invite erroneously passed by a caller cannot hydrate queue state.
        context = AuthorizationContext(
            user_id=ALPHA_USER_ID,
            organization=OrganizationScope(ALPHA_ORGANIZATION_ID),
            email="synthetic@example.invalid",
            name="Synthetic",
            role=InternalUserRole.RECRUITER,
        )
        invites = session.scalars(select(AssessmentInvite)).all()
        assert all(
            item.delivery_state is None for item in invitation_responses(session, context, invites)
        )
    for path, headers, identifier in [
        (PATH, alpha_headers, local),
        (f"/v1/roles/{BEACON_ROLE_ID}/invites", beacon_headers, foreign),
    ]:
        response = await invitation_client.get(path, headers=headers)
        assert response.status_code == 200
        assert [(item["id"], item["delivery_state"]) for item in response.json()["items"]] == [
            (identifier, None)
        ]
    assert (await invitation_client.get(PATH, headers=beacon_headers)).status_code == 404


@pytest.mark.anyio
async def test_legacy_create_and_revoke_include_null(
    invitation_client: AsyncClient,
    alpha_headers: dict[str, str],
) -> None:
    created = await invitation_client.post(
        PATH,
        headers=alpha_headers,
        json={
            "role_profile_id": str(ALPHA_PROFILE_ID),
            "email": "synthetic@example.invalid",
        },
    )
    assert created.status_code == 201
    assert created.json()["delivery_state"] is None
    assert created.json()["status"] == "active"
    revoked = await invitation_client.post(
        f"{PATH}/{created.json()['id']}/revoke", headers=alpha_headers
    )
    assert revoked.status_code == 200
    assert revoked.json()["delivery_state"] is None
    assert revoked.json()["status"] == "revoked"


@pytest.mark.anyio
async def test_create_response_hydrates_queue_and_revoke_returns_cancelled(
    invitation_client: AsyncClient,
    invitation_session_factory: sessionmaker[Session],
    alpha_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identifier = seed_invites(invitation_session_factory, 1)[0]
    with invitation_session_factory() as session:
        add_delivery(session, identifier, DeliveryState.QUEUED)
        session.commit()

    def existing(self: InternalInvitationService, *args: Any, **kwargs: Any) -> AssessmentInvite:
        invite = self._session.get(AssessmentInvite, UUID(identifier))
        assert invite is not None
        return invite

    # Exercise response hydration without running the PostgreSQL-only issuance queue.
    monkeypatch.setattr(InternalInvitationService, "create", existing)
    created = await invitation_client.post(
        PATH,
        headers=alpha_headers,
        json={
            "role_profile_id": str(ALPHA_PROFILE_ID),
            "email": "synthetic@example.invalid",
        },
    )
    assert created.status_code == 201
    assert created.json()["delivery_state"] == "queued"
    revoked = await invitation_client.post(f"{PATH}/{identifier}/revoke", headers=alpha_headers)
    assert revoked.status_code == 200
    assert revoked.json()["delivery_state"] == "cancelled"
    assert revoked.json()["status"] == "revoked"
