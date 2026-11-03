"""Verify Auth0 API access tokens using its rotating public signing keys."""

import jwt
from jwt import PyJWKClient

from app.auth.tokens import TokenIdentity, TokenValidationError


class Auth0TokenVerifier:
    """Pin RS256, issuer and API audience; resolve tenant/permissions from storage.

    The JWKS location comes only from server configuration, never JWT headers.
    PyJWT caches the key set and refreshes on unknown key IDs for key rotation.
    """

    def __init__(self, *, issuer: str, audience: str, leeway_seconds: int) -> None:
        """Require a secure issuer before any provider network request."""

        from urllib.parse import urlsplit

        url = urlsplit(issuer)
        if (
            url.scheme != "https"
            or not url.hostname
            or url.query
            or url.fragment
            or url.username is not None
        ):
            raise ValueError("Auth0 issuer must be an HTTPS URL without credentials/query/fragment")
        self._issuer = issuer.rstrip("/") + "/"
        self._audience = audience
        self._leeway = leeway_seconds
        self._keys = PyJWKClient(self._issuer + ".well-known/jwks.json", timeout=5, lifespan=300)

    def verify(self, token: str) -> TokenIdentity:
        """Reject malformed/expired/foreign tokens and unavailable signing keys."""

        if len(token) > 16_384:
            raise TokenValidationError("token is too large")
        try:
            key = self._keys.get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                key.key,
                algorithms=["RS256"],
                issuer=self._issuer,
                audience=self._audience,
                leeway=self._leeway,
                options={"require": ["exp", "iat", "iss", "aud", "sub"]},
            )
            subject = claims["sub"]
            if not isinstance(subject, str) or not subject.strip() or len(subject) > 255:
                raise TokenValidationError("invalid subject")
        except jwt.PyJWTError as exc:
            raise TokenValidationError("invalid provider token") from exc
        # Auth0 claims cannot assign application tenants or permissions.
        return TokenIdentity(subject=subject, organization_id=None)
