"""Unit tests for strict internal-user JWT verification and settings."""

import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest
from pydantic import SecretStr, ValidationError

from app.auth.config import AuthenticationSettings
from app.auth.tokens import HmacJwtVerifier, TokenIdentity, TokenValidationError

SECRET = "test-only-authentication-secret-0123456789"
ISSUER = "https://issuer.example.invalid"
AUDIENCE = "iopsych-api-test"
ORGANIZATION_ID = UUID("10000000-0000-4000-8000-000000000001")


def _encode_segment(value: object) -> str:
    """Encode compact JSON using the JWT base64url convention."""

    raw = json.dumps(value, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def make_token(
    *,
    header: dict[str, object] | None = None,
    claims: dict[str, object] | None = None,
    secret: str = SECRET,
    remove_claims: tuple[str, ...] = (),
) -> str:
    """Sign a deterministic test JWT without adding a production minting API."""

    now = int(datetime.now(UTC).timestamp())
    resolved_claims: dict[str, object] = {
        "sub": "provider-user-1",
        "organization_id": str(ORGANIZATION_ID),
        "iss": ISSUER,
        "aud": AUDIENCE,
        "iat": now,
        "nbf": now - 1,
        "exp": now + 300,
    }
    if claims:
        resolved_claims.update(claims)
    for claim_name in remove_claims:
        resolved_claims.pop(claim_name, None)
    encoded_header = _encode_segment(header or {"alg": "HS256", "typ": "JWT"})
    encoded_claims = _encode_segment(resolved_claims)
    signing_input = f"{encoded_header}.{encoded_claims}"
    signature = hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).digest()
    encoded_signature = base64.urlsafe_b64encode(signature).rstrip(b"=").decode()
    return f"{signing_input}.{encoded_signature}"


@pytest.fixture
def verifier() -> HmacJwtVerifier:
    """Provide the strictly configured production verifier."""

    return HmacJwtVerifier(
        secret=SECRET,
        issuer=ISSUER,
        audience=AUDIENCE,
        leeway_seconds=0,
    )


def test_verifier_accepts_string_and_array_audiences(verifier: HmacJwtVerifier) -> None:
    """Both audience encodings allowed by JWT are accepted."""

    assert verifier.verify(make_token()) == TokenIdentity(
        subject="provider-user-1", organization_id=ORGANIZATION_ID
    )
    assert verifier.verify(make_token(claims={"aud": ["another", AUDIENCE]})).subject == (
        "provider-user-1"
    )


@pytest.mark.parametrize(
    ("token", "match"),
    [
        ("x" * 16_385, "too large"),
        ("not-a-jwt", "malformed"),
        ("e30.e30.%%%", "malformed"),
        (make_token(header={"alg": "none", "typ": "JWT"}), "header"),
        (make_token(header={"alg": "HS256", "typ": "NOT-JWT"}), "header"),
        (make_token(secret="wrong-but-long-test-secret-0123456789"), "signature"),
        (make_token(claims={"exp": 0}), "expired"),
        (make_token(claims={"nbf": 9_999_999_999}), "not active"),
        (make_token(claims={"iat": 9_999_999_999}), "future"),
        (make_token(claims={"iss": "wrong"}), "issuer or audience"),
        (make_token(claims={"aud": ["wrong"]}), "issuer or audience"),
        (make_token(claims={"aud": [AUDIENCE, 3]}), "issuer or audience"),
        (make_token(claims={"sub": ""}), "subject"),
        (make_token(claims={"sub": 3}), "subject"),
        (make_token(claims={"organization_id": 3}), "organization"),
        (make_token(claims={"organization_id": "not-a-uuid"}), "organization"),
        (make_token(claims={"exp": True}), "exp"),
        (make_token(claims={"exp": float("nan")}), "exp"),
        (make_token(claims={"exp": "tomorrow"}), "exp"),
        (make_token(claims={"nbf": "yesterday"}), "nbf"),
    ],
)
def test_verifier_rejects_invalid_tokens(verifier: HmacJwtVerifier, token: str, match: str) -> None:
    """Malformed, untrusted, and out-of-window tokens all fail verification."""

    with pytest.raises(TokenValidationError, match=match):
        verifier.verify(token)


def test_verifier_rejects_invalid_json_shapes(verifier: HmacJwtVerifier) -> None:
    """JWT header and claims segments must be valid JSON objects."""

    valid = make_token().split(".")
    for encoded_value in (
        base64.urlsafe_b64encode(b"not-json").rstrip(b"=").decode(),
        _encode_segment(["not", "an", "object"]),
        base64.urlsafe_b64encode(b"\xff").rstrip(b"=").decode(),
    ):
        token = f"{encoded_value}.{valid[1]}.{valid[2]}"
        with pytest.raises(TokenValidationError):
            verifier.verify(token)


def test_optional_time_claims_can_be_absent_and_expiry_is_required(
    verifier: HmacJwtVerifier,
) -> None:
    """Only expiry is mandatory; provider omission of iat/nbf is supported."""

    token = make_token(remove_claims=("iat", "nbf"))
    header_segment, payload_segment, _ = token.split(".")
    claims: dict[str, Any] = json.loads(
        base64.urlsafe_b64decode(payload_segment + "=" * (-len(payload_segment) % 4))
    )
    assert verifier.verify(token).subject == "provider-user-1"

    claims.pop("exp")
    # ``make_token`` merges claims into defaults, so build the missing-expiry
    # payload directly while retaining a valid signature.
    encoded_claims = _encode_segment(claims)
    signing_input = f"{header_segment}.{encoded_claims}"
    signature = hmac.new(SECRET.encode(), signing_input.encode(), hashlib.sha256).digest()
    missing_expiry = f"{signing_input}.{base64.urlsafe_b64encode(signature).rstrip(b'=').decode()}"
    with pytest.raises(TokenValidationError, match="exp"):
        verifier.verify(missing_expiry)


def test_authentication_settings_validate_secrets_and_identifiers() -> None:
    """Configuration accepts secure values and rejects weak or blank ones."""

    settings = AuthenticationSettings(
        jwt_secret=SecretStr(SECRET),
        jwt_issuer=ISSUER,
        jwt_audience=AUDIENCE,
    )
    assert settings.jwt_secret is not None
    assert settings.jwt_issuer == ISSUER

    with pytest.raises(ValidationError, match="at least 32 bytes"):
        AuthenticationSettings(jwt_secret=SecretStr("short"))
    with pytest.raises(ValidationError, match="cannot be blank"):
        AuthenticationSettings(jwt_issuer="   ")


@pytest.mark.parametrize(
    ("secret", "issuer", "audience", "leeway_seconds"),
    [
        ("short", ISSUER, AUDIENCE, 0),
        (SECRET, " ", AUDIENCE, 0),
        (SECRET, ISSUER, " ", 0),
        (SECRET, ISSUER, AUDIENCE, 301),
    ],
)
def test_verifier_rejects_unsafe_direct_configuration(
    secret: str, issuer: str, audience: str, leeway_seconds: int
) -> None:
    """Direct verifier construction enforces the same security floor as settings."""

    with pytest.raises(ValueError):
        HmacJwtVerifier(
            secret=secret,
            issuer=issuer,
            audience=audience,
            leeway_seconds=leeway_seconds,
        )
