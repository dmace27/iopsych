"""Policy and database-authoritative checks for local synthetic login."""

from collections.abc import Iterator
from typing import cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.auth.config import AuthenticationSettings
from app.database.models import User
from app.database.seed import ALPHA_USER_ID, BEACON_ROLE_ID
from app.database.session import create_session_factory
from app.main import create_app


@pytest.fixture
def local_client(database_engine: Engine, seeded_session: Session) -> Iterator[TestClient]:
    settings = AuthenticationSettings(
        _env_file=None,
        local_login_enabled=True,
        environment="development",
        jwt_secret=SecretStr("local-test-secret-that-is-at-least-32-bytes"),
    )
    app = create_app(
        authentication_settings=settings, session_factory=create_session_factory(database_engine)
    )
    with TestClient(app, base_url="http://127.0.0.1:8101", client=("127.0.0.1", 1234)) as client:
        yield client


def test_synthetic_login_and_tenant_isolation(local_client: TestClient) -> None:
    for identity in ("alpha", "beacon"):
        response = local_client.post("/v1/auth/local-login", json={"identity": identity})
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
        me = local_client.get("/v1/auth/me", headers=headers)
        assert me.status_code == 200
        assert me.json()["email"].endswith(".example.invalid")
        if identity == "alpha":
            assert (
                local_client.get(f"/v1/roles/{BEACON_ROLE_ID}", headers=headers).status_code == 404
            )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("local_login_enabled", False),
        ("environment", "production"),
        ("local_web_origin", "https://hosted.example"),
        ("local_web_origin", "https://localhost:3101"),
        ("jwt_secret", None),
    ],
)
def test_disabled_policy(local_client: TestClient, field: str, value: object) -> None:
    setattr(cast(FastAPI, local_client.app).state.authentication_settings, field, value)
    assert local_client.post("/v1/auth/local-login", json={"identity": "alpha"}).status_code == 404


def test_untrusted_requests(local_client: TestClient) -> None:
    for headers in ({"Host": "hosted.example"}, {"Origin": "https://attacker.example"}):
        assert (
            local_client.post(
                "/v1/auth/local-login", json={"identity": "alpha"}, headers=headers
            ).status_code
            == 404
        )
    with TestClient(
        local_client.app, base_url="http://localhost", client=("203.0.113.1", 1234)
    ) as remote:
        assert remote.post("/v1/auth/local-login", json={"identity": "alpha"}).status_code == 404
    with TestClient(local_client.app, base_url="http://localhost", client=None) as missing:  # type: ignore[arg-type]
        assert missing.post("/v1/auth/local-login", json={"identity": "alpha"}).status_code == 404


def test_rejects_arbitrary_identity(local_client: TestClient) -> None:
    for payload in ({"identity": "admin"}, {"identity": "alpha", "role": "admin"}):
        assert local_client.post("/v1/auth/local-login", json=payload).status_code == 422


@pytest.mark.parametrize("change", ["missing", "subject", "email", "tenant"])
def test_seed_identity_must_match(
    local_client: TestClient, seeded_session: Session, change: str
) -> None:
    user = seeded_session.get(User, ALPHA_USER_ID)
    assert user is not None
    if change == "missing":
        # A temporary different ID avoids deleting seed records with FK references.
        cast(FastAPI, local_client.app).state.session_factory = lambda: MissingUserSession()
    elif change == "subject":
        user.auth_subject = "real-user"
    elif change == "email":
        user.email = "real@example.com"
    else:
        from app.database.seed import BEACON_ORGANIZATION_ID

        user.organization_id = BEACON_ORGANIZATION_ID
    seeded_session.commit()
    assert local_client.post("/v1/auth/local-login", json={"identity": "alpha"}).status_code == 401


class MissingUserSession(Session):
    def get(self, *args: object, **kwargs: object) -> None:
        return None
