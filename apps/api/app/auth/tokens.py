"""Minimal, strict verification for provider-issued HS256 JWT bearer tokens."""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID


class TokenValidationError(ValueError):
    """Signal any invalid token without carrying user-visible detail."""


@dataclass(frozen=True)
class TokenIdentity:
    """Verified identity claims needed to resolve an internal user."""

    subject: str
    organization_id: UUID


class TokenVerifier(Protocol):
    """Provider-neutral interface consumed by the authentication dependency."""

    def verify(self, token: str) -> TokenIdentity:
        """Verify a bearer token and return its trusted identity claims."""


class HmacJwtVerifier:
    """Verify only explicitly configured HS256 JWTs.

    Algorithm selection is never read from configuration or inferred from the
    token. Pinning HS256 prevents algorithm-confusion and unsigned-token bugs.
    """

    def __init__(self, *, secret: str, issuer: str, audience: str, leeway_seconds: int) -> None:
        """Store immutable validation parameters for one trusted issuer."""

        if len(secret.encode()) < 32:
            raise ValueError("JWT HMAC secrets must contain at least 32 bytes")
        if not issuer.strip() or not audience.strip():
            raise ValueError("JWT issuer and audience cannot be blank")
        if not 0 <= leeway_seconds <= 300:
            raise ValueError("JWT leeway must be between 0 and 300 seconds")
        self._secret = secret.encode()
        self._issuer = issuer
        self._audience = audience
        self._leeway_seconds = leeway_seconds

    def verify(self, token: str) -> TokenIdentity:
        """Validate signature, registered claims, subject, and tenant claim."""

        if len(token) > 16_384:
            raise TokenValidationError("token is too large")
        try:
            header_segment, payload_segment, signature_segment = token.split(".")
            header = _decode_json_object(header_segment)
            claims = _decode_json_object(payload_segment)
            signature = _decode_base64url(signature_segment)
            signing_input = f"{header_segment}.{payload_segment}".encode("ascii")
        except (ValueError, UnicodeError) as exc:
            raise TokenValidationError("token is malformed") from exc

        if header.get("alg") != "HS256" or header.get("typ", "JWT") != "JWT":
            raise TokenValidationError("token header is not supported")

        expected_signature = hmac.new(self._secret, signing_input, hashlib.sha256).digest()
        if not hmac.compare_digest(signature, expected_signature):
            raise TokenValidationError("token signature is invalid")

        now = datetime.now(UTC).timestamp()
        _validate_timestamp_claims(claims, now=now, leeway_seconds=self._leeway_seconds)
        if claims.get("iss") != self._issuer or not _has_audience(claims, self._audience):
            raise TokenValidationError("token issuer or audience is invalid")

        subject = claims.get("sub")
        organization_id = claims.get("organization_id")
        if not isinstance(subject, str) or not subject.strip():
            raise TokenValidationError("token subject is invalid")
        if not isinstance(organization_id, str):
            raise TokenValidationError("token organization is invalid")
        try:
            parsed_organization_id = UUID(organization_id)
        except ValueError as exc:
            raise TokenValidationError("token organization is invalid") from exc
        return TokenIdentity(subject=subject, organization_id=parsed_organization_id)


def _decode_base64url(segment: str) -> bytes:
    """Decode one unpadded base64url segment with strict alphabet checks."""

    padding = "=" * (-len(segment) % 4)
    try:
        return base64.b64decode(segment + padding, altchars=b"-_", validate=True)
    except (binascii.Error, ValueError) as exc:
        raise TokenValidationError("token segment is malformed") from exc


def _decode_json_object(segment: str) -> dict[str, object]:
    """Decode a JWT JSON segment and require an object at the top level."""

    try:
        value = json.loads(_decode_base64url(segment))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise TokenValidationError("token JSON is malformed") from exc
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise TokenValidationError("token JSON must be an object")
    return value


def _numeric_claim(claims: Mapping[str, object], name: str, *, required: bool) -> float | None:
    """Read a numeric date while rejecting booleans and absent required claims."""

    value = claims.get(name)
    if value is None and not required:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
        raise TokenValidationError(f"token {name} is invalid")
    return float(value)


def _validate_timestamp_claims(
    claims: Mapping[str, object], *, now: float, leeway_seconds: int
) -> None:
    """Require expiry and reject tokens used outside their valid time window."""

    expires_at = _numeric_claim(claims, "exp", required=True)
    not_before = _numeric_claim(claims, "nbf", required=False)
    issued_at = _numeric_claim(claims, "iat", required=False)
    assert expires_at is not None  # Narrowed by the required numeric-claim check above.
    if expires_at <= now - leeway_seconds:
        raise TokenValidationError("token is expired")
    if not_before is not None and not_before > now + leeway_seconds:
        raise TokenValidationError("token is not active")
    if issued_at is not None and issued_at > now + leeway_seconds:
        raise TokenValidationError("token issue time is in the future")


def _has_audience(claims: Mapping[str, object], expected: str) -> bool:
    """Accept the standard string or string-array JWT audience forms."""

    audience = claims.get("aud")
    if isinstance(audience, str):
        return hmac.compare_digest(audience, expected)
    if isinstance(audience, list) and all(isinstance(item, str) for item in audience):
        return any(hmac.compare_digest(item, expected) for item in audience)
    return False
