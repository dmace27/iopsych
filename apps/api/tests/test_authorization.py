"""API tests for authentication, RBAC, organization isolation, and auditing."""

from collections.abc import AsyncGenerator
from typing import Annotated
from uuid import UUID

import pytest
from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient
from sqlalchemy import Engine, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app.audit import AuditMiddleware, audited, get_audit_policy
from app.auth.config import AuthenticationSettings
from app.auth.context import AuthorizationContext, OrganizationScope
from app.auth.dependencies import get_organization_data_access, require_roles
from app.auth.errors import AccessProblemError, organization_resource_not_found
from app.database.models import AuditEvent, InternalUserRole, User
from app.database.repositories import OrganizationDataAccess
from app.database.seed import (
    ALPHA_ORGANIZATION_ID,
    ALPHA_ROLE_ID,
    ALPHA_USER_ID,
    BEACON_ORGANIZATION_ID,
    BEACON_ROLE_ID,
    seed_database,
)
from app.database.session import REQUEST_SESSION_STATE_ATTRIBUTE, create_session_factory
from app.main import create_app
from tests.test_auth_tokens import AUDIENCE, ISSUER, SECRET, make_token

ADMIN_USER_ID = UUID("10000000-0000-4000-8000-000000000099")


@pytest.fixture
def anyio_backend() -> str:
    """Use asyncio for every HTTP authorization test."""

    return "asyncio"


@pytest.fixture
def api_session_factory(database_engine: Engine) -> sessionmaker[Session]:
    """Seed auth subjects and an administrator in the shared test database."""

    factory = create_session_factory(database_engine)
    with factory() as session:
        seed_database(session)
        session.commit()
        alpha = session.get(User, ALPHA_USER_ID)
        beacon = OrganizationDataAccess(session, BEACON_ORGANIZATION_ID).list_users()[0]
        assert alpha is not None
        alpha.auth_subject = "provider-alpha"
        beacon.auth_subject = "provider-beacon"
        session.add(
            User(
                id=ADMIN_USER_ID,
                organization_id=ALPHA_ORGANIZATION_ID,
                email="admin@alpha.example.invalid",
                name="Alpha Admin",
                auth_subject="provider-admin",
                role=InternalUserRole.ADMIN,
            )
        )
        session.commit()
    return factory


@pytest.fixture
def auth_app(api_session_factory: sessionmaker[Session]) -> FastAPI:
    """Build the API and test-only protected routes from production helpers."""

    settings = AuthenticationSettings(
        jwt_secret=SECRET,
        jwt_issuer=ISSUER,
        jwt_audience=AUDIENCE,
        jwt_leeway_seconds=0,
    )
    application = create_app(
        authentication_settings=settings,
        session_factory=api_session_factory,
    )

    @application.get("/test/recruiter")
    @audited("test.recruiter_read", "user")
    async def recruiter_only(
        context: Annotated[
            AuthorizationContext,
            Depends(require_roles(InternalUserRole.RECRUITER)),
        ],
    ) -> dict[str, str]:
        """Expose a recruiter-only policy for black-box tests."""

        return {"role": context.role.value}

    @application.get("/test/roles/{role_id}")
    @audited("test.role_read", "role", entity_id_path_parameter="role_id")
    async def read_role(
        role_id: UUID,
        data: Annotated[OrganizationDataAccess, Depends(get_organization_data_access)],
    ) -> dict[str, str]:
        """Read a role only through the current organization's repository."""

        role = data.get_role(role_id)
        if role is None:
            raise organization_resource_not_found()
        return {"title": role.title}

    @application.get("/test/misconfigured-audit")
    @audited("test.audit_target", "role", entity_id_path_parameter="missing")
    async def misconfigured_audit_target(
        context: Annotated[
            AuthorizationContext,
            Depends(require_roles(InternalUserRole.RECRUITER)),
        ],
    ) -> dict[str, str]:
        """Exercise safe audit attribution for a missing UUID path value."""

        return {"actor": str(context.user_id)}

    @application.get("/test/upstream-failure")
    @audited("test.upstream_failure", "user")
    async def upstream_failure(
        context: Annotated[
            AuthorizationContext,
            Depends(require_roles(InternalUserRole.RECRUITER)),
        ],
    ) -> JSONResponse:
        """Expose a failed sensitive outcome so its audit label is verified."""

        del context
        return JSONResponse(status_code=503, content={"available": False})

    @application.get("/test/raised-failure")
    @audited("test.raised_failure", "user")
    async def raised_failure(
        context: Annotated[
            AuthorizationContext,
            Depends(require_roles(InternalUserRole.RECRUITER)),
        ],
    ) -> None:
        """Raise after authentication to verify exception-path auditing."""

        del context
        raise RuntimeError("synthetic endpoint failure")

    return application


@pytest.fixture
async def client(auth_app: FastAPI) -> AsyncGenerator[AsyncClient]:
    """Provide an in-process client for the configured authorization API."""

    async with AsyncClient(
        transport=ASGITransport(app=auth_app), base_url="http://test"
    ) as api_client:
        yield api_client


def auth_header(subject: str, organization_id: UUID, **claims: object) -> dict[str, str]:
    """Build an authorization header for a provider identity and tenant."""

    token_claims = {"sub": subject, "organization_id": str(organization_id), **claims}
    return {"Authorization": f"Bearer {make_token(claims=token_claims)}"}


@pytest.mark.anyio
async def test_current_user_requires_authentication_and_fails_closed_without_config(
    client: AsyncClient,
    api_session_factory: sessionmaker[Session],
) -> None:
    """Missing credentials and missing server config cannot access internal data."""

    response = await client.get("/v1/auth/me")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "authentication_required"

    unavailable_app = create_app(
        authentication_settings=AuthenticationSettings(jwt_secret=None),
        session_factory=api_session_factory,
    )
    async with AsyncClient(
        transport=ASGITransport(app=unavailable_app), base_url="http://test"
    ) as unavailable_client:
        unavailable = await unavailable_client.get(
            "/v1/auth/me", headers={"Authorization": "Bearer anything"}
        )
    assert unavailable.status_code == 503
    assert unavailable.json()["code"] == "authentication_unavailable"


@pytest.mark.anyio
async def test_current_user_uses_database_identity_and_emits_success_audit(
    client: AsyncClient,
    api_session_factory: sessionmaker[Session],
) -> None:
    """A valid token resolves current tenant/role state and creates an audit event."""

    # A forged token role is ignored because RBAC reads the database user.
    response = await client.get(
        "/v1/auth/me",
        headers=auth_header(
            "provider-alpha", ALPHA_ORGANIZATION_ID, role=InternalUserRole.ADMIN.value
        ),
    )
    assert response.status_code == 200
    assert response.json() == {
        "id": str(ALPHA_USER_ID),
        "organization_id": str(ALPHA_ORGANIZATION_ID),
        "email": "recruiter@alpha.example.invalid",
        "name": "Alpha Recruiter",
        "role": "recruiter",
    }

    with api_session_factory() as session:
        event = session.scalar(
            select(AuditEvent).where(AuditEvent.event_type == "internal_user.session_read")
        )
        assert event is not None
        assert event.organization_id == ALPHA_ORGANIZATION_ID
        assert event.actor_id == ALPHA_USER_ID
        assert event.entity_id == ALPHA_USER_ID
        assert event.metadata_json == {
            "http_method": "GET",
            "http_status": 200,
            "outcome": "succeeded",
        }


@pytest.mark.anyio
async def test_invalid_token_and_cross_organization_identity_are_rejected(
    client: AsyncClient,
) -> None:
    """Bad signatures and a real subject paired to another tenant both return 401."""

    bad_signature = make_token(secret="different-test-secret-that-is-long-enough")
    invalid = await client.get("/v1/auth/me", headers={"Authorization": f"Bearer {bad_signature}"})
    cross_tenant = await client.get(
        "/v1/auth/me",
        headers=auth_header("provider-alpha", BEACON_ORGANIZATION_ID),
    )
    assert invalid.status_code == cross_tenant.status_code == 401
    assert invalid.json() == cross_tenant.json()


@pytest.mark.anyio
async def test_rbac_denies_unlisted_roles_and_audits_rejection(
    client: AsyncClient,
    api_session_factory: sessionmaker[Session],
) -> None:
    """Role policies are explicit and rejected authenticated attempts are audited."""

    allowed = await client.get(
        "/test/recruiter", headers=auth_header("provider-alpha", ALPHA_ORGANIZATION_ID)
    )
    denied_manager = await client.get(
        "/test/recruiter", headers=auth_header("provider-beacon", BEACON_ORGANIZATION_ID)
    )
    denied_admin = await client.get(
        "/test/recruiter", headers=auth_header("provider-admin", ALPHA_ORGANIZATION_ID)
    )
    assert allowed.status_code == 200
    assert denied_manager.status_code == denied_admin.status_code == 403
    assert denied_manager.json()["code"] == "permission_denied"

    with api_session_factory() as session:
        events = list(
            session.scalars(
                select(AuditEvent)
                .where(AuditEvent.event_type == "test.recruiter_read")
                .order_by(AuditEvent.created_at, AuditEvent.id)
            )
        )
        assert sorted(event.metadata_json["outcome"] for event in events) == [
            "rejected",
            "rejected",
            "succeeded",
        ]


@pytest.mark.anyio
async def test_organization_scoped_route_hides_cross_tenant_resource(
    client: AsyncClient,
    api_session_factory: sessionmaker[Session],
) -> None:
    """Knowing another organization's role UUID never grants read access."""

    own = await client.get(
        f"/test/roles/{ALPHA_ROLE_ID}",
        headers=auth_header("provider-alpha", ALPHA_ORGANIZATION_ID),
    )
    foreign = await client.get(
        f"/test/roles/{BEACON_ROLE_ID}",
        headers=auth_header("provider-alpha", ALPHA_ORGANIZATION_ID),
    )
    assert own.status_code == 200
    assert foreign.status_code == 404
    assert foreign.json()["code"] == "resource_not_found"

    with api_session_factory() as session:
        foreign_event = session.scalar(
            select(AuditEvent).where(
                AuditEvent.event_type == "test.role_read",
                AuditEvent.entity_id == BEACON_ROLE_ID,
            )
        )
        assert foreign_event is not None
        assert foreign_event.organization_id == ALPHA_ORGANIZATION_ID
        assert foreign_event.metadata_json["outcome"] == "rejected"


@pytest.mark.anyio
async def test_invalid_audit_target_falls_back_to_authenticated_actor(
    client: AsyncClient,
    api_session_factory: sessionmaker[Session],
) -> None:
    """A route-policy mistake cannot suppress audit attribution."""

    response = await client.get(
        "/test/misconfigured-audit",
        headers=auth_header("provider-alpha", ALPHA_ORGANIZATION_ID),
    )
    assert response.status_code == 200
    with api_session_factory() as session:
        event = session.scalar(
            select(AuditEvent).where(AuditEvent.event_type == "test.audit_target")
        )
        assert event is not None
        assert event.entity_id == ALPHA_USER_ID
        assert event.metadata_json["target_path_parameter_valid"] is False


@pytest.mark.anyio
async def test_failed_sensitive_response_is_audited(
    client: AsyncClient,
    api_session_factory: sessionmaker[Session],
) -> None:
    """Server failures on sensitive endpoints retain a distinct audit outcome."""

    response = await client.get(
        "/test/upstream-failure",
        headers=auth_header("provider-alpha", ALPHA_ORGANIZATION_ID),
    )
    assert response.status_code == 503
    with api_session_factory() as session:
        event = session.scalar(
            select(AuditEvent).where(AuditEvent.event_type == "test.upstream_failure")
        )
        assert event is not None
        assert event.metadata_json["outcome"] == "failed"


@pytest.mark.anyio
async def test_raised_sensitive_exception_is_audited_before_propagation(
    client: AsyncClient,
    api_session_factory: sessionmaker[Session],
) -> None:
    """Unhandled failures retain an audit event even when error middleware renders the 500."""

    with pytest.raises(RuntimeError, match="synthetic endpoint failure"):
        await client.get(
            "/test/raised-failure",
            headers=auth_header("provider-alpha", ALPHA_ORGANIZATION_ID),
        )

    with api_session_factory() as session:
        event = session.scalar(
            select(AuditEvent).where(AuditEvent.event_type == "test.raised_failure")
        )
        assert event is not None
        assert event.metadata_json == {
            "http_method": "GET",
            "http_status": 500,
            "outcome": "failed",
        }


def test_organization_scope_and_policy_configuration_helpers() -> None:
    """Tenant matching and decorator validation enforce safe defaults."""

    scope = OrganizationScope(ALPHA_ORGANIZATION_ID)
    scope.require_matches(ALPHA_ORGANIZATION_ID)
    with pytest.raises(AccessProblemError) as error:
        scope.require_matches(BEACON_ORGANIZATION_ID)
    assert error.value.status == 404

    with pytest.raises(ValueError, match="at least one"):
        require_roles()
    with pytest.raises(ValueError, match="cannot be blank"):
        audited("", "role")

    @audited("test.action", "role")
    def sample_endpoint() -> None:
        """Provide a decorated endpoint for metadata inspection."""

    policy = get_audit_policy(sample_endpoint)
    assert policy is not None
    assert policy.event_type == "test.action"
    assert get_audit_policy(object()) is None


class _FailingSessionContext:
    """Context manager that simulates an unavailable audit database."""

    def __enter__(self) -> Session:
        """Raise the same database-family error caught by the middleware."""

        raise OperationalError("insert", {}, Exception("offline"))

    def __exit__(self, *args: object) -> None:
        """Satisfy the context-manager interface; entry always raises."""


class _FailingSessionFactory:
    """Callable stand-in for a sessionmaker whose database is unavailable."""

    def __call__(self) -> _FailingSessionContext:
        """Return the failing context manager."""

        return _FailingSessionContext()


@pytest.mark.anyio
async def test_audit_failure_returns_problem_instead_of_sensitive_response() -> None:
    """A mandatory audit-write failure causes the endpoint to fail closed."""

    application = FastAPI()
    application.add_middleware(
        AuditMiddleware,
        session_factory=_FailingSessionFactory(),  # type: ignore[arg-type]
    )

    @application.get("/sensitive")
    @audited("test.failure", "user")
    async def sensitive(request: Request) -> dict[str, bool]:
        """Set the same verified context that auth normally stores."""

        request.state.authorization_context = AuthorizationContext(
            user_id=ALPHA_USER_ID,
            organization=OrganizationScope(ALPHA_ORGANIZATION_ID),
            email="recruiter@alpha.example.invalid",
            name="Alpha Recruiter",
            role=InternalUserRole.RECRUITER,
        )
        return {"sensitive": True}

    @application.get("/failing-sensitive")
    @audited("test.raised_failure", "user")
    async def failing_sensitive(request: Request) -> None:
        """Prove audit persistence still fails closed during endpoint errors."""

        request.state.authorization_context = AuthorizationContext(
            user_id=ALPHA_USER_ID,
            organization=OrganizationScope(ALPHA_ORGANIZATION_ID),
            email="recruiter@alpha.example.invalid",
            name="Alpha Recruiter",
            role=InternalUserRole.RECRUITER,
        )
        raise RuntimeError("the audit failure must replace this detail")

    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as audit_client:
        response = await audit_client.get("/sensitive")
        raised_response = await audit_client.get("/failing-sensitive")
    assert response.status_code == 500
    assert response.json()["code"] == "audit_persistence_failed"
    assert raised_response.status_code == 500
    assert raised_response.json()["code"] == "audit_persistence_failed"


@pytest.mark.anyio
async def test_audited_endpoint_without_domain_session_uses_isolated_writer(
    api_session_factory: sessionmaker[Session],
) -> None:
    """Read-only audited handlers can persist without opening a domain session."""

    application = FastAPI()
    application.add_middleware(AuditMiddleware, session_factory=api_session_factory)

    @application.get("/isolated-audit")
    @audited("test.isolated", "user")
    async def isolated_audit(request: Request) -> dict[str, bool]:
        """Attach a verified actor without requesting a database dependency."""

        request.state.authorization_context = AuthorizationContext(
            user_id=ALPHA_USER_ID,
            organization=OrganizationScope(ALPHA_ORGANIZATION_ID),
            email="recruiter@alpha.example.invalid",
            name="Alpha Recruiter",
            role=InternalUserRole.RECRUITER,
        )
        return {"audited": True}

    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as audit_client:
        response = await audit_client.get("/isolated-audit")

    assert response.status_code == 200
    with api_session_factory() as session:
        assert (
            session.scalar(select(AuditEvent).where(AuditEvent.event_type == "test.isolated"))
            is not None
        )


@pytest.mark.anyio
async def test_unaudited_request_commit_failure_is_not_mislabeled(
    api_session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A non-audit database failure propagates instead of returning an audit problem."""

    application = FastAPI()
    application.add_middleware(AuditMiddleware, session_factory=api_session_factory)

    @application.post("/ordinary-write")
    async def ordinary_write(request: Request) -> dict[str, bool]:
        """Attach a request session to exercise middleware commit propagation."""

        setattr(
            request.state,
            REQUEST_SESSION_STATE_ATTRIBUTE,
            api_session_factory(),
        )
        return {"written": True}

    def fail_commit(session: Session) -> None:
        del session
        raise OperationalError("commit", {}, Exception("offline"))

    monkeypatch.setattr(Session, "commit", fail_commit)
    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as audit_client:
        with pytest.raises(OperationalError, match="offline"):
            await audit_client.post("/ordinary-write")
