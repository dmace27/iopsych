"""FastAPI application factory and entry point for the IOPsych service."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends, FastAPI
from pydantic import BaseModel
from sqlalchemy.orm import Session, sessionmaker

from app.audit import AuditMiddleware, audited
from app.auth.config import AuthenticationSettings
from app.auth.context import AuthorizationContext
from app.auth.dependencies import require_roles
from app.auth.errors import AccessProblemError, access_problem_handler
from app.auth.tokens import HmacJwtVerifier, TokenVerifier
from app.database.models import InternalUserRole
from app.database.session import create_database_engine, create_session_factory


class HealthResponse(BaseModel):
    """Stable response contract for service health probes."""

    status: Literal["ok"]
    service: Literal["api"]
    version: str


class CurrentUserResponse(BaseModel):
    """Safe account and authorization context returned to the signed-in user."""

    id: UUID
    organization_id: UUID
    email: str
    name: str
    role: InternalUserRole


def create_app(
    *,
    authentication_settings: AuthenticationSettings | None = None,
    session_factory: sessionmaker[Session] | None = None,
    token_verifier: TokenVerifier | None = None,
) -> FastAPI:
    """Create an application with injectable auth and database boundaries."""

    settings = authentication_settings or AuthenticationSettings()
    resolved_session_factory = session_factory or create_session_factory(create_database_engine())
    resolved_verifier = token_verifier
    if resolved_verifier is None and settings.jwt_secret is not None:
        resolved_verifier = HmacJwtVerifier(
            secret=settings.jwt_secret.get_secret_value(),
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
            leeway_seconds=settings.jwt_leeway_seconds,
        )

    application = FastAPI(
        title="IOPsych API",
        description="API foundation for the consented, human-reviewed IOPsych pilot.",
        version="0.1.0",
    )
    application.state.session_factory = resolved_session_factory
    application.state.token_verifier = resolved_verifier
    application.add_exception_handler(AccessProblemError, access_problem_handler)
    application.add_middleware(AuditMiddleware, session_factory=resolved_session_factory)

    @application.get("/health", response_model=HealthResponse, tags=["operations"])
    async def health() -> HealthResponse:
        """Return a dependency-free liveness response for local and hosted probes."""

        return HealthResponse(status="ok", service="api", version=application.version)

    @application.get("/v1/auth/me", response_model=CurrentUserResponse, tags=["authentication"])
    @audited("internal_user.session_read", "user")
    async def current_user(
        context: Annotated[
            AuthorizationContext,
            Depends(
                require_roles(
                    InternalUserRole.ADMIN,
                    InternalUserRole.RECRUITER,
                    InternalUserRole.HIRING_MANAGER,
                )
            ),
        ],
    ) -> CurrentUserResponse:
        """Return the current database-authoritative user and tenant context."""

        return CurrentUserResponse(
            id=context.user_id,
            organization_id=context.organization.organization_id,
            email=context.email,
            name=context.name,
            role=context.role,
        )

    return application


# The module-level ASGI app defers database connections and fails closed on
# internal routes if AUTH_JWT_SECRET has not been configured.
app = create_app()
