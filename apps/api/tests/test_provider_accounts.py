"""Identity-provider verification and account lifecycle regression coverage."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.auth.auth0 import Auth0TokenVerifier
from app.auth.bootstrap import bootstrap_administrator
from app.auth.config import AuthenticationSettings
from app.auth.context import AuthorizationContext, OrganizationScope
from app.auth.errors import AccessProblemError
from app.auth.users import UserInput, _lock_administrator
from app.database.models import AuditEvent, InternalUserRole, User
from app.database.seed import ALPHA_ORGANIZATION_ID, ALPHA_USER_ID, BEACON_USER_ID
from app.database.session import create_session_factory
from app.main import create_app
from tests.test_auth_tokens import AUDIENCE, ISSUER, make_token
from tests.test_authorization import (
    ADMIN_USER_ID,
)
from tests.test_authorization import (
    api_session_factory as api_session_factory,
)
from tests.test_authorization import (
    auth_app as auth_app,
)


@pytest.fixture
def anyio_backend() -> str:
    """Run HTTP tests with asyncio."""
    return "asyncio"


def headers(subject: str = "provider-admin") -> dict[str, str]:
    """Supply an existing seeded account with a signed development token."""
    return {
        "Authorization": "Bearer "
        + make_token(claims={"sub": subject, "organization_id": str(ALPHA_ORGANIZATION_ID)})
    }


@pytest.mark.anyio
async def test_administrator_account_lifecycle(
    auth_app: FastAPI, api_session_factory: sessionmaker[Session]
) -> None:
    """Provision, change permissions, disable and re-enable through audited routes."""
    async with AsyncClient(transport=ASGITransport(app=auth_app), base_url="http://test") as client:
        payload = {
            "auth_subject": "provider-new",
            "email": "new@alpha.example.invalid",
            "name": "New Manager",
            "role": "hiring_manager",
        }
        created = await client.post("/v1/users", json=payload, headers=headers())
        assert created.status_code == 201, created.text
        account = created.json()
        assert account["is_active"] is True
        assert account["organization_id"] == str(ALPHA_ORGANIZATION_ID)
        assert (await client.get("/v1/auth/me", headers=headers("provider-new"))).json()[
            "role"
        ] == "hiring_manager"
        assert len((await client.get("/v1/users?limit=1&offset=0", headers=headers())).json()) == 1
        assert (await client.get("/v1/users?limit=101", headers=headers())).status_code == 422
        for role, active in [("recruiter", True), ("recruiter", False), ("hiring_manager", True)]:
            response = await client.patch(
                f"/v1/users/{account['id']}",
                headers=headers(),
                json={"role": role, "is_active": active, "expected_version": account["version"]},
            )
            assert response.status_code == 200
            account = response.json()
            me = await client.get("/v1/auth/me", headers=headers("provider-new"))
            assert me.status_code == (200 if active else 401)
            if active:
                assert me.json()["role"] == role
        assert (await client.post("/v1/users", json=payload, headers=headers())).status_code == 409
        # Globally reserved subjects reveal no cross-tenant identity details.
        payload["auth_subject"] = "provider-beacon"
        payload["email"] = "other@alpha.example.invalid"
        assert (await client.post("/v1/users", json=payload, headers=headers())).status_code == 409
        change = {"role": "admin", "is_active": False, "expected_version": 1}
        assert (
            await client.patch(f"/v1/users/{BEACON_USER_ID}", json=change, headers=headers())
        ).status_code == 404
        assert (
            await client.patch(f"/v1/users/{ADMIN_USER_ID}", json=change, headers=headers())
        ).status_code == 403
        for method, path, body in [
            ("GET", "/v1/users", None),
            ("POST", "/v1/users", payload),
            ("PATCH", f"/v1/users/{account['id']}", change),
        ]:
            assert (
                await client.request(method, path, json=body, headers=headers("provider-alpha"))
            ).status_code == 403
    with api_session_factory() as session:
        events = list(
            session.scalars(
                select(AuditEvent).where(AuditEvent.event_type == "internal_user.provision")
            )
        )
        assert len(events) == 4
        assert events[0].entity_id == UUID(account["id"])
        assert "provider-new" not in str([event.metadata_json for event in events])
        actor = session.get(User, ADMIN_USER_ID)
        assert actor is not None
        actor.is_active = False
        session.flush()
        context = AuthorizationContext(
            user_id=actor.id,
            organization=OrganizationScope(actor.organization_id),
            email=actor.email,
            name=actor.name,
            role=InternalUserRole.ADMIN,
        )
        with pytest.raises(AccessProblemError):
            _lock_administrator(session, context)
        actor.is_active = True
        actor.role = InternalUserRole.RECRUITER
        session.flush()
        with pytest.raises(AccessProblemError):
            _lock_administrator(session, context)


def test_operator_bootstrap(database_engine: Engine) -> None:
    """Bootstrap is atomic, audited and cannot overwrite an existing tenant."""
    factory = create_session_factory(database_engine)
    account = UserInput(
        auth_subject="auth0|operator",
        email="admin@example.invalid",
        name="Pilot Admin",
        role="admin",
    )
    with factory.begin() as session:
        user = bootstrap_administrator(
            session, slug="pilot", organization_name="Pilot", account=account
        )
        assert user.is_active and user.role == InternalUserRole.ADMIN
        assert session.scalar(select(AuditEvent).where(AuditEvent.actor_id == user.id)) is not None
        with pytest.raises(ValueError, match="already exists"):
            bootstrap_administrator(
                session, slug="pilot", organization_name="Overwrite", account=account
            )


def test_auth0_signatures_claims_rotation_and_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    """Use real RSA signatures and the real JWKS key selector without provider traffic."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    second = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key(), as_dict=True)
    assert isinstance(jwk, dict)
    jwk.update(kid="first", use="sig", alg="RS256")
    verifier = Auth0TokenVerifier(issuer=ISSUER, audience=AUDIENCE, leeway_seconds=0)
    monkeypatch.setattr(verifier._keys, "fetch_data", lambda: {"keys": [jwk]})
    now = int(datetime.now(UTC).timestamp())
    claims = {
        "sub": "provider-alpha",
        "iss": ISSUER + "/",
        "aud": AUDIENCE,
        "iat": now,
        "exp": now + 300,
        "organization_id": "untrusted-tenant",
        "role": "admin",
    }

    def token(**overrides: Any) -> str:
        return jwt.encode(claims | overrides, key, algorithm="RS256", headers={"kid": "first"})

    identity = verifier.verify(token())
    assert identity.subject == "provider-alpha" and identity.organization_id is None
    for bad in [
        "x" * 16385,
        "malformed",
        token(exp=0),
        token(iss="wrong"),
        token(aud="wrong"),
        token(sub=""),
        token(sub=" " * 2),
        token(sub=1),
        token(sub="x" * 256),
        token(iat=now + 300),
        jwt.encode(claims, second, algorithm="RS256", headers={"kid": "first"}),
        jwt.encode(
            claims,
            "untrusted-but-long-test-secret-0123456789",
            algorithm="HS256",
            headers={"kid": "first"},
        ),
        jwt.encode(
            {k: v for k, v in claims.items() if k != "exp"},
            key,
            algorithm="RS256",
            headers={"kid": "first"},
        ),
    ]:
        with pytest.raises(ValueError):
            verifier.verify(bad)
    # A newly published key ID is fetched and accepted without process restart.
    rotated = jwt.algorithms.RSAAlgorithm.to_jwk(second.public_key(), as_dict=True)
    assert isinstance(rotated, dict)
    rotated.update(kid="second", use="sig", alg="RS256")
    monkeypatch.setattr(verifier._keys, "fetch_data", lambda: {"keys": [rotated]})
    assert (
        verifier.verify(
            jwt.encode(claims, second, algorithm="RS256", headers={"kid": "second"})
        ).subject
        == "provider-alpha"
    )

    def offline(token: str) -> Any:
        raise jwt.PyJWKClientConnectionError("private network detail")

    monkeypatch.setattr(verifier._keys, "get_signing_key_from_jwt", offline)
    with pytest.raises(ValueError, match="invalid provider token"):
        verifier.verify(token())
    for issuer in [
        "http://issuer.invalid",
        "https:///",
        "https://user@issuer.invalid",
        "https://issuer.invalid/?query=x",
        "https://issuer.invalid/#fragment",
    ]:
        with pytest.raises(ValueError, match="HTTPS"):
            Auth0TokenVerifier(issuer=issuer, audience=AUDIENCE, leeway_seconds=0)


@pytest.mark.anyio
async def test_auth0_resolves_database_tenant_and_revoked_account(
    api_session_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Provider tokens need no tenant claim; disabled/unknown accounts fail closed."""
    app = create_app(
        session_factory=api_session_factory,
        authentication_settings=AuthenticationSettings(
            provider="auth0", jwt_issuer=ISSUER, jwt_audience=AUDIENCE
        ),
    )
    from app.auth.tokens import TokenIdentity

    monkeypatch.setattr(
        app.state.token_verifier, "verify", lambda token: TokenIdentity(token, None)
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/v1/auth/me", headers={"Authorization": "Bearer provider-alpha"}
        )
        assert response.json()["organization_id"] == str(ALPHA_ORGANIZATION_ID)
        assert (
            await client.get("/v1/auth/me", headers={"Authorization": "Bearer unknown"})
        ).status_code == 401
        with api_session_factory.begin() as session:
            user = session.get(User, ALPHA_USER_ID)
            assert user is not None
            user.is_active = False
        assert (
            await client.get("/v1/auth/me", headers={"Authorization": "Bearer provider-alpha"})
        ).status_code == 401


@pytest.mark.anyio
async def test_account_provisioning_rolls_back_when_audit_commit_fails(
    auth_app: FastAPI,
    api_session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An account must not survive a failed mandatory account-provisioning audit."""
    from sqlalchemy.exc import OperationalError

    def fail_commit(session: Session) -> None:
        """Simulate a database failure at the middleware's atomic commit boundary."""
        raise OperationalError("commit", {}, Exception("offline"))

    monkeypatch.setattr(Session, "commit", fail_commit)
    async with AsyncClient(transport=ASGITransport(app=auth_app), base_url="http://test") as client:
        response = await client.post(
            "/v1/users",
            headers=headers(),
            json={
                "auth_subject": "must-rollback",
                "email": "rollback@alpha.example.invalid",
                "name": "Rollback",
                "role": "recruiter",
            },
        )
        assert response.status_code == 500
        assert response.json()["code"] == "audit_persistence_failed"
    with api_session_factory() as session:
        assert session.scalar(select(User).where(User.auth_subject == "must-rollback")) is None
