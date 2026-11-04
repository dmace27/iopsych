"""Synthetic, isolated invitation history contract and security tests."""

from __future__ import annotations

# ruff: noqa: F811 -- pytest fixture parameters intentionally shadow imports.
import base64
from datetime import UTC, datetime, timedelta
from unittest.mock import patch
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.database.models import (
    AssessmentInvite,
    AssessmentInviteStatus,
    AuditEvent,
    InternalUserRole,
    User,
)
from app.database.seed import ALPHA_PROFILE_ID, ALPHA_ROLE_ID, ALPHA_USER_ID, BEACON_ROLE_ID
from tests.test_invitations import (  # noqa: F401
    ARCHIVED_PROFILE_ID,
    ARCHIVED_ROLE_ID,
    DRAFT_PROFILE_ID,
    alpha_headers,
    anyio_backend,
    beacon_headers,
    build_app,
    delivery,
    invitation_client,
    invitation_session_factory,
    invitation_settings,
)

PATH = f"/v1/roles/{ALPHA_ROLE_ID}/invites"
NOW = datetime(2026, 11, 4, 12, tzinfo=UTC)


def seed_invites(
    factory: sessionmaker[Session],
    count: int,
    profile: UUID = ALPHA_PROFILE_ID,
    offset: int = 0,
    created_at: datetime = NOW,
) -> list[str]:
    """Use deterministic tied timestamps to exercise the UUID ordering key."""
    ids = []
    with factory() as session:
        for number in range(offset + 1, offset + count + 1):
            invite_id = UUID(int=number)
            ids.append(str(invite_id))
            session.add(
                AssessmentInvite(
                    id=invite_id,
                    role_profile_id=profile,
                    email=f"synthetic-{number}@example.invalid",
                    token_hash=f"{number:064x}",
                    created_at=created_at,
                    expires_at=NOW + timedelta(days=1),
                    status=list(AssessmentInviteStatus)[number % len(AssessmentInviteStatus)],
                )
            )
        session.commit()
    return list(reversed(ids))


@pytest.mark.anyio
async def test_pages_ties_insertions_and_safe_shape(
    invitation_client: AsyncClient,
    invitation_session_factory: sessionmaker[Session],
    alpha_headers: dict[str, str],
) -> None:
    expected = seed_invites(invitation_session_factory, 5)
    first = await invitation_client.get(PATH, headers=alpha_headers, params={"limit": 2})
    assert first.status_code == 200
    assert first.headers["cache-control"] == "no-store"
    body = first.json()
    assert [item["id"] for item in body["items"]] == expected[:2]
    assert set(body["items"][0]) == {
        "id",
        "role_profile_id",
        "email",
        "expires_at",
        "status",
        "delivery_state",
        "sent_at",
        "revoked_at",
        "created_at",
    }
    cursor = body["next_cursor"]
    assert len(cursor) == 102
    decoded = base64.urlsafe_b64decode(cursor + "==")
    assert b"example.invalid" not in decoded and b"synthetic" not in decoded
    seed_invites(invitation_session_factory, 1, offset=100, created_at=NOW + timedelta(hours=1))
    seen = [item["id"] for item in body["items"]]
    while cursor:
        response = await invitation_client.get(
            PATH, headers=alpha_headers, params={"limit": 2, "cursor": cursor}
        )
        assert response.status_code == 200
        seen.extend(item["id"] for item in response.json()["items"])
        cursor = response.json()["next_cursor"]
    assert seen == expected
    with invitation_session_factory() as session:
        audits = session.scalars(
            select(AuditEvent).where(AuditEvent.event_type == "assessment_invite.listed")
        ).all()
        assert len(audits) == 3
        assert all(event.entity_id == ALPHA_ROLE_ID for event in audits)
        assert all(
            set(event.metadata_json) == {"http_method", "http_status", "outcome"}
            for event in audits
        )


@pytest.mark.anyio
async def test_default_max_empty_and_archived(
    invitation_client: AsyncClient,
    invitation_session_factory: sessionmaker[Session],
    alpha_headers: dict[str, str],
) -> None:
    assert (await invitation_client.get(PATH, headers=alpha_headers)).json() == {
        "items": [],
        "next_cursor": None,
    }
    seed_invites(invitation_session_factory, 101)
    default = await invitation_client.get(PATH, headers=alpha_headers)
    assert len(default.json()["items"]) == 25
    maximum = await invitation_client.get(PATH, headers=alpha_headers, params={"limit": 100})
    assert len(maximum.json()["items"]) == 100
    assert maximum.json()["next_cursor"]
    seed_invites(invitation_session_factory, 1, ARCHIVED_PROFILE_ID, offset=200)
    archived = await invitation_client.get(
        f"/v1/roles/{ARCHIVED_ROLE_ID}/invites", headers=alpha_headers
    )
    assert archived.status_code == 200 and len(archived.json()["items"]) == 1


@pytest.mark.anyio
@pytest.mark.parametrize("limit", [0, 101, -1, "a", "2.5"])
async def test_limit_bounds(
    invitation_client: AsyncClient, alpha_headers: dict[str, str], limit: int | str
) -> None:
    response = await invitation_client.get(PATH, headers=alpha_headers, params={"limit": limit})
    assert response.status_code == 422
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.anyio
@pytest.mark.parametrize("cursor", ["", "x", "x" * 10000, "!" * 102, "A" * 102])
async def test_bad_cursor_is_generic(
    invitation_client: AsyncClient, alpha_headers: dict[str, str], cursor: str
) -> None:
    response = await invitation_client.get(PATH, headers=alpha_headers, params={"cursor": cursor})
    assert response.status_code == 422
    assert response.json()["code"] == "invalid_invitation_cursor"
    assert response.json()["detail"] == "The invitation cursor is invalid."
    assert "errors" not in response.json()


@pytest.mark.anyio
async def test_cursor_scope_and_tampering(
    invitation_client: AsyncClient,
    invitation_session_factory: sessionmaker[Session],
    alpha_headers: dict[str, str],
    beacon_headers: dict[str, str],
) -> None:
    seed_invites(invitation_session_factory, 3)
    first = await invitation_client.get(PATH, headers=alpha_headers, params={"limit": 1})
    cursor = first.json()["next_cursor"]
    for path, headers in [
        (f"/v1/roles/{ARCHIVED_ROLE_ID}/invites", alpha_headers),
        (f"/v1/roles/{BEACON_ROLE_ID}/invites", beacon_headers),
    ]:
        response = await invitation_client.get(path, headers=headers, params={"cursor": cursor})
        assert response.status_code == 422
    raw = base64.urlsafe_b64decode(cursor + "==")
    for index in [0, 33, 60, 75]:
        changed = bytearray(raw)
        changed[index] ^= 1
        forged = base64.urlsafe_b64encode(changed).rstrip(b"=").decode()
        response = await invitation_client.get(
            PATH, headers=alpha_headers, params={"cursor": forged}
        )
        assert response.status_code == 422
    # Noncanonical unused padding bits must not create an alternate cursor.
    forged = cursor[:-1] + ("B" if cursor[-1] == "A" else "R")
    assert (
        await invitation_client.get(PATH, headers=alpha_headers, params={"cursor": forged})
    ).status_code == 422


@pytest.mark.anyio
async def test_permissions_and_hidden_roles(
    invitation_client: AsyncClient,
    invitation_session_factory: sessionmaker[Session],
    alpha_headers: dict[str, str],
    beacon_headers: dict[str, str],
) -> None:
    assert (await invitation_client.get(PATH)).status_code == 401
    foreign = await invitation_client.get(PATH, headers=beacon_headers)
    missing = await invitation_client.get(
        f"/v1/roles/{UUID(int=999)}/invites", headers=beacon_headers
    )
    assert foreign.status_code == missing.status_code == 404
    assert foreign.json()["detail"] == missing.json()["detail"]
    for role, expected in [(InternalUserRole.ADMIN, 200), (InternalUserRole.HIRING_MANAGER, 403)]:
        with invitation_session_factory() as session:
            user = session.get(User, ALPHA_USER_ID)
            assert user is not None
            user.role = role
            session.commit()
        assert (await invitation_client.get(PATH, headers=alpha_headers)).status_code == expected


@pytest.mark.anyio
async def test_unconfigured_delivery_and_rate_limit(
    invitation_session_factory: sessionmaker[Session], alpha_headers: dict[str, str]
) -> None:
    seed_invites(invitation_session_factory, 2)
    app = build_app(
        invitation_session_factory,
        None,
        settings=invitation_settings(token_signing_secret=None, internal_rate_limit=2),
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        first = await client.get(PATH, headers=alpha_headers, params={"limit": 1})
        assert first.status_code == 200
        assert (
            await client.get(
                PATH, headers=alpha_headers, params={"cursor": first.json()["next_cursor"]}
            )
        ).status_code == 200
        limited = await client.get(PATH, headers=alpha_headers)
        assert limited.status_code == 429 and limited.headers["retry-after"]
        assert limited.headers["cache-control"] == "no-store"


@pytest.mark.anyio
async def test_all_profile_versions_and_timestamp_order(
    invitation_client: AsyncClient,
    invitation_session_factory: sessionmaker[Session],
    alpha_headers: dict[str, str],
) -> None:
    newer = seed_invites(invitation_session_factory, 1)
    older = seed_invites(
        invitation_session_factory,
        1,
        DRAFT_PROFILE_ID,
        offset=500,
        created_at=NOW - timedelta(days=1),
    )
    response = await invitation_client.get(PATH, headers=alpha_headers, params={"limit": 1})
    assert [item["id"] for item in response.json()["items"]] == newer
    response = await invitation_client.get(
        PATH, headers=alpha_headers, params={"cursor": response.json()["next_cursor"]}
    )
    assert [item["id"] for item in response.json()["items"]] == older
    assert response.json()["next_cursor"] is None


@pytest.mark.anyio
async def test_audit_failure_withholds_discovery(
    invitation_client: AsyncClient,
    alpha_headers: dict[str, str],
) -> None:
    with patch(
        "app.audit.Session.commit", side_effect=SQLAlchemyError("synthetic internal detail")
    ):
        response = await invitation_client.get(PATH, headers=alpha_headers)
    assert response.status_code == 500
    assert response.json()["code"] == "audit_persistence_failed"
    assert "synthetic internal detail" not in response.text
    assert response.headers["cache-control"] == "no-store"
