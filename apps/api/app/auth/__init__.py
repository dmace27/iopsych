"""Authentication and authorization primitives for internal API users."""

from app.auth.config import AuthenticationSettings
from app.auth.context import AuthorizationContext, OrganizationScope
from app.auth.dependencies import authenticate_internal_user, require_roles
from app.auth.tokens import HmacJwtVerifier, TokenIdentity, TokenVerifier

__all__ = [
    "AuthenticationSettings",
    "AuthorizationContext",
    "HmacJwtVerifier",
    "OrganizationScope",
    "TokenIdentity",
    "TokenVerifier",
    "authenticate_internal_user",
    "require_roles",
]
