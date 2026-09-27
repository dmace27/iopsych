"""Opaque, signed invite-token generation and one-way database fingerprints."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from dataclasses import dataclass

TOKEN_CONTEXT = b"iopsych-candidate-invite-v1:"
TOKEN_SECRET_BYTES = 32
SIGNATURE_BYTES = 32


class InvalidInviteTokenError(ValueError):
    """Raised when an invite token is malformed or fails signature validation."""


@dataclass(frozen=True)
class GeneratedInviteToken:
    """Hold the transient bearer value and the only value safe for persistence."""

    raw_token: str
    token_hash: str


class InviteTokenCodec:
    """Create signed bearer tokens and resolve them to SHA-256 fingerprints."""

    def __init__(self, signing_secret: str) -> None:
        """Bind a server-held key with at least 256 bits of material."""

        encoded = signing_secret.encode()
        if len(encoded) < 32:
            raise ValueError("invite signing secret must contain at least 32 bytes")
        self._signing_secret = encoded

    def generate(self) -> GeneratedInviteToken:
        """Generate 32 random bytes, sign them, and return a persistence hash."""

        secret = _encode(secrets.token_bytes(TOKEN_SECRET_BYTES))
        signature = self._signature(secret)
        raw_token = f"{secret}.{_encode(signature)}"
        return GeneratedInviteToken(raw_token=raw_token, token_hash=_hash(raw_token))

    def validate_and_hash(self, raw_token: str) -> str:
        """Validate token shape/signature and return its database lookup hash."""

        try:
            secret, encoded_signature = raw_token.split(".")
            secret_bytes = _decode(secret)
            signature = _decode(encoded_signature)
        except (ValueError, UnicodeError) as exc:
            raise InvalidInviteTokenError("invalid invite token") from exc
        if len(secret_bytes) != TOKEN_SECRET_BYTES or len(signature) != SIGNATURE_BYTES:
            raise InvalidInviteTokenError("invalid invite token")
        if not hmac.compare_digest(signature, self._signature(secret)):
            raise InvalidInviteTokenError("invalid invite token")
        return _hash(raw_token)

    def _signature(self, encoded_secret: str) -> bytes:
        """Sign the encoded secret with a versioned domain separator."""

        return hmac.digest(
            self._signing_secret,
            TOKEN_CONTEXT + encoded_secret.encode("ascii"),
            "sha256",
        )


def opaque_rate_limit_key(raw_token: str) -> str:
    """Hash untrusted path input before it can enter in-memory limiter state."""

    return _hash(raw_token)


def _hash(value: str) -> str:
    """Create the fixed-width one-way fingerprint persisted for lookup."""

    return hashlib.sha256(value.encode()).hexdigest()


def _encode(value: bytes) -> str:
    """Return URL-safe base64 without optional padding."""

    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    """Decode strict URL-safe base64 while restoring its optional padding."""

    if not value or any(character not in _URLSAFE_CHARACTERS for character in value):
        raise ValueError("invalid base64url")
    padding = "=" * (-len(value) % 4)
    decoded = base64.b64decode(value + padding, altchars=b"-_", validate=True)
    # Reject alternate encodings that differ only in unused padding bits. A
    # canonical representation prevents multiple bearer strings from mapping
    # to one signed value and keeps rate-limit/hash identity unambiguous.
    if _encode(decoded) != value:
        raise ValueError("non-canonical base64url")
    return decoded


_URLSAFE_CHARACTERS = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_")
