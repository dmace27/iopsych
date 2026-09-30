"""FastAPI application factory and entry point for the IOPsych service."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends, FastAPI
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel
from sqlalchemy.orm import Session, sessionmaker

from app.audit import AuditMiddleware, audited
from app.auth.config import AuthenticationSettings
from app.auth.context import AuthorizationContext
from app.auth.dependencies import require_roles
from app.auth.errors import (
    AccessProblemError,
    access_problem_handler,
    request_validation_problem_handler,
)
from app.auth.tokens import HmacJwtVerifier, TokenVerifier
from app.database.models import InternalUserRole
from app.database.session import create_database_engine, create_session_factory
from app.extraction.config import RoleExtractionSettings
from app.extraction.provider import (
    RoleExtractionProvider,
    build_role_extraction_provider,
)
from app.invitations.config import InvitationSettings
from app.invitations.delivery import (
    InvitationDeliveryAdapter,
    UnconfiguredInvitationDelivery,
)
from app.invitations.logging import install_invite_token_log_filter
from app.invitations.rate_limit import InMemoryRateLimiter
from app.invitations.router import router as invitations_router
from app.invitations.tokens import InviteTokenCodec
from app.privacy.config import PrivacySettings
from app.privacy.router import candidate_router as candidate_privacy_router
from app.privacy.router import privacy_router
from app.reports.router import router as reports_router
from app.reports.router import submission_router
from app.roles.router import router as roles_router
from app.security import SecurityMiddleware, unexpected_problem_handler


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
    invitation_settings: InvitationSettings | None = None,
    invitation_delivery: InvitationDeliveryAdapter | None = None,
    invitation_rate_limiter: InMemoryRateLimiter | None = None,
    role_extraction_settings: RoleExtractionSettings | None = None,
    role_extraction_provider: RoleExtractionProvider | None = None,
    privacy_settings: PrivacySettings | None = None,
    session_factory: sessionmaker[Session] | None = None,
    token_verifier: TokenVerifier | None = None,
) -> FastAPI:
    """Create an application with injectable auth and database boundaries."""

    settings = authentication_settings or AuthenticationSettings()
    invite_settings = invitation_settings or InvitationSettings()
    extraction_settings = role_extraction_settings or RoleExtractionSettings()
    resolved_privacy_settings = privacy_settings or PrivacySettings()
    install_invite_token_log_filter()
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
    application.state.invitation_settings = invite_settings
    application.state.invitation_delivery = invitation_delivery or UnconfiguredInvitationDelivery()
    application.state.invitation_rate_limiter = invitation_rate_limiter or InMemoryRateLimiter()
    application.state.role_extraction_settings = extraction_settings
    application.state.role_extraction_provider = (
        role_extraction_provider or build_role_extraction_provider(extraction_settings)
    )
    application.state.privacy_settings = resolved_privacy_settings
    application.state.invite_token_codec = (
        InviteTokenCodec(invite_settings.token_signing_secret.get_secret_value())
        if invite_settings.token_signing_secret is not None
        else None
    )
    application.add_exception_handler(Exception, unexpected_problem_handler)
    application.add_exception_handler(AccessProblemError, access_problem_handler)
    application.add_exception_handler(RequestValidationError, request_validation_problem_handler)
    application.add_middleware(AuditMiddleware, session_factory=resolved_session_factory)
    application.add_middleware(SecurityMiddleware)
    application.include_router(roles_router)
    application.include_router(invitations_router)
    application.include_router(reports_router)
    application.include_router(submission_router)
    application.include_router(candidate_privacy_router)
    application.include_router(privacy_router)

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
