"""FastAPI dependencies for bearer authentication, RBAC, and tenant access."""

from collections.abc import Callable, Generator
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth.context import AuthorizationContext, OrganizationScope
from app.auth.errors import authentication_required, authentication_unavailable, permission_denied
from app.auth.tokens import TokenValidationError, TokenVerifier
from app.database.models import InternalUserRole
from app.database.repositories import OrganizationDataAccess

bearer_scheme = HTTPBearer(auto_error=False)


def get_database_session(request: Request) -> Generator[Session]:
    """Yield a request-scoped database session from the application factory."""

    factory = request.app.state.session_factory
    with factory() as session:
        yield session


def authenticate_internal_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    session: Annotated[Session, Depends(get_database_session)],
) -> AuthorizationContext:
    """Authenticate a token and resolve fresh role and tenant state from storage."""

    verifier: TokenVerifier | None = request.app.state.token_verifier
    if verifier is None:
        raise authentication_unavailable()
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise authentication_required()
    try:
        identity = verifier.verify(credentials.credentials)
    except TokenValidationError as exc:
        # Never disclose whether signature, expiry, subject, or tenant failed.
        raise authentication_required() from exc

    organization_access = OrganizationDataAccess(session, identity.organization_id)
    user = organization_access.get_user_by_auth_subject(identity.subject)
    if user is None:
        raise authentication_required()

    context = AuthorizationContext(
        user_id=user.id,
        organization=OrganizationScope(user.organization_id),
        email=user.email,
        name=user.name,
        role=user.role,
    )
    # Audit middleware reads only this validated, database-backed context.
    request.state.authorization_context = context
    return context


RoleDependency = Callable[..., AuthorizationContext]


def require_roles(*allowed_roles: InternalUserRole) -> RoleDependency:
    """Build a least-privilege dependency for an explicit set of roles.

    Administrators are not an implicit super-role. Callers must list ``ADMIN``
    when an administrator should be able to perform the protected action.
    """

    if not allowed_roles:
        raise ValueError("at least one allowed role is required")
    allowed = frozenset(allowed_roles)

    def authorize_role(
        context: Annotated[AuthorizationContext, Depends(authenticate_internal_user)],
    ) -> AuthorizationContext:
        """Return the context only when its current database role is allowed."""

        if context.role not in allowed:
            raise permission_denied()
        return context

    return authorize_role


def get_organization_data_access(
    context: Annotated[AuthorizationContext, Depends(authenticate_internal_user)],
    session: Annotated[Session, Depends(get_database_session)],
) -> OrganizationDataAccess:
    """Create a repository that cannot query outside the authenticated tenant."""

    return OrganizationDataAccess(session, context.organization.organization_id)
