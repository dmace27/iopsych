"""Tenant isolation, fresh permissions, and atomic account access audits."""

from collections.abc import AsyncGenerator, Sequence
from typing import Any
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.database.models import AuditEvent, InternalUserRole, User
from app.database.seed import ALPHA_ORGANIZATION_ID, ALPHA_USER_ID, BEACON_ORGANIZATION_ID
from tests.test_authorization import (
    ADMIN_USER_ID,
    anyio_backend,
    api_session_factory,
    auth_app,
    auth_header,
)

__all__ = ["anyio_backend", "api_session_factory", "auth_app"]
BASE = "/v1/accounts/users"
ADMIN = auth_header("provider-admin", ALPHA_ORGANIZATION_ID)


@pytest.fixture
async def account_client(auth_app: FastAPI) -> AsyncGenerator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=auth_app), base_url="http://test") as client:
        yield client


@pytest.mark.anyio
async def test_discovery_bounds_and_tenant_cursor(
    account_client: AsyncClient, api_session_factory: sessionmaker[Session]
) -> None:
    page = await account_client.get(BASE, headers=ADMIN, params={"limit": 1})
    assert page.status_code == 200
    assert page.headers["cache-control"] == "no-store"
    body = page.json()
    assert len(body["items"]) == 1
    assert set(body["items"][0]) == {"id", "email", "name", "role", "is_active", "version"}
    next_page = await account_client.get(
        BASE, headers=ADMIN, params={"limit": 1, "after": body["next_cursor"]}
    )
    assert next_page.status_code == 200
    assert next_page.json()["next_cursor"] is None
    with api_session_factory() as session:
        foreign = session.scalar(select(User).where(User.organization_id == BEACON_ORGANIZATION_ID))
        assert foreign is not None
        foreign_id = foreign.id
    for cursor in [foreign_id, uuid4()]:
        response = await account_client.get(BASE, headers=ADMIN, params={"after": str(cursor)})
        assert response.status_code == 404
        assert response.json()["code"] == "resource_not_found"
    for limit in [0, 101]:
        assert (
            await account_client.get(BASE, headers=ADMIN, params={"limit": limit})
        ).status_code == 422


@pytest.mark.anyio
async def test_role_disable_reactivate_and_version(
    account_client: AsyncClient, api_session_factory: sessionmaker[Session]
) -> None:
    target = f"{BASE}/{ALPHA_USER_ID}"
    recruiter = auth_header("provider-alpha", ALPHA_ORGANIZATION_ID, role="admin")
    assert (await account_client.get(BASE, headers=recruiter)).status_code == 403
    changed = await account_client.patch(
        target, headers=ADMIN, json={"expected_version": 1, "role": "admin"}
    )
    assert changed.status_code == 200
    assert changed.json()["version"] == 2
    assert (await account_client.get(BASE, headers=recruiter)).status_code == 200
    stale = await account_client.patch(
        target, headers=ADMIN, json={"expected_version": 1, "is_active": False}
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "account_version_conflict"
    disabled = await account_client.patch(
        target, headers=ADMIN, json={"expected_version": 2, "is_active": False}
    )
    assert disabled.status_code == 200
    assert (await account_client.get("/v1/auth/me", headers=recruiter)).status_code == 401
    enabled = await account_client.patch(
        target, headers=ADMIN, json={"expected_version": 3, "is_active": True, "role": "recruiter"}
    )
    assert enabled.status_code == 200
    assert (await account_client.get("/v1/auth/me", headers=recruiter)).status_code == 200
    assert (await account_client.get(BASE, headers=recruiter)).status_code == 403
    noop = await account_client.patch(
        target, headers=ADMIN, json={"expected_version": 4, "is_active": True}
    )
    assert noop.json()["version"] == 4
    with api_session_factory() as session:
        changes = list(
            session.scalars(
                select(AuditEvent).where(AuditEvent.event_type == "account.access_changed")
            )
        )
        assert len(changes) == 3
        assert changes[0].metadata_json["before"]["version"] == 1
        for event in changes:
            assert event.actor_id == ADMIN_USER_ID
            assert event.entity_id == ALPHA_USER_ID
            assert set(event.metadata_json) == {"before", "after"}
            assert set(event.metadata_json["after"]) == {"role", "is_active", "version"}


@pytest.mark.anyio
async def test_self_mutation_and_foreign_targets_rejected(
    account_client: AsyncClient, api_session_factory: sessionmaker[Session]
) -> None:
    changes: list[dict[str, object]] = [
        {"role": "recruiter"},
        {"is_active": False},
        {"role": "admin"},
    ]
    for change in changes:
        response = await account_client.patch(
            f"{BASE}/{ADMIN_USER_ID}", headers=ADMIN, json={"expected_version": 1, **change}
        )
        assert response.status_code == 403
    with api_session_factory() as session:
        foreign = session.scalar(select(User).where(User.organization_id == BEACON_ORGANIZATION_ID))
        assert foreign is not None
        foreign_id = foreign.id
    for target in [foreign_id, uuid4()]:
        response = await account_client.patch(
            f"{BASE}/{target}", headers=ADMIN, json={"expected_version": 1, "role": "admin"}
        )
        assert response.status_code == 404
    with api_session_factory() as session:
        admin = session.get(User, ADMIN_USER_ID)
        assert admin is not None and admin.is_active and admin.role == InternalUserRole.ADMIN
        assert admin.version == 1
        assert not list(
            session.scalars(
                select(AuditEvent).where(AuditEvent.event_type == "account.access_changed")
            )
        )


@pytest.mark.anyio
async def test_audit_failure_rolls_back_change(
    account_client: AsyncClient,
    api_session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from sqlalchemy.exc import OperationalError

    original_flush = Session.flush

    def failed_flush(self: Session, objects: Sequence[Any] | None = None) -> None:
        if any(
            isinstance(row, AuditEvent) and row.event_type == "account.access_changed"
            for row in self.new
        ):
            raise OperationalError("synthetic", {}, RuntimeError("audit unavailable"))
        original_flush(self, objects)

    monkeypatch.setattr(Session, "flush", failed_flush)
    with pytest.raises(OperationalError):
        await account_client.patch(
            f"{BASE}/{ALPHA_USER_ID}",
            headers=ADMIN,
            json={"expected_version": 1, "is_active": False},
        )
    with api_session_factory() as session:
        user = session.get(User, ALPHA_USER_ID)
        assert user is not None and user.is_active and user.version == 1


@pytest.mark.anyio
@pytest.mark.parametrize("role", [InternalUserRole.RECRUITER, InternalUserRole.HIRING_MANAGER])
async def test_non_admin_cannot_mutate_even_with_admin_token_claim(
    account_client: AsyncClient, api_session_factory: sessionmaker[Session], role: InternalUserRole
) -> None:
    with api_session_factory() as session:
        user = session.get(User, ALPHA_USER_ID)
        assert user is not None
        user.role = role
        session.commit()
    headers = auth_header("provider-alpha", ALPHA_ORGANIZATION_ID, role="admin")
    assert (await account_client.get(BASE, headers=headers)).status_code == 403
    response = await account_client.patch(
        f"{BASE}/{ADMIN_USER_ID}",
        headers=headers,
        json={"expected_version": 1, "is_active": False},
    )
    assert response.status_code == 403


@pytest.mark.anyio
async def test_unknown_and_null_fields_rejected_over_http(account_client: AsyncClient) -> None:
    invalid_fields: list[dict[str, object]] = [
        {"email": "new@example.invalid"},
        {"role": None},
        {"is_active": None},
    ]
    for extra in invalid_fields:
        response = await account_client.patch(
            f"{BASE}/{ALPHA_USER_ID}",
            headers=ADMIN,
            json={"expected_version": 1, **extra},
        )
        assert response.status_code == 422
    assert (await account_client.post(BASE, headers=ADMIN, json={})).status_code == 405
