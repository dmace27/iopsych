"""Authenticated, bounded credential envelopes for local invitation delivery."""

from __future__ import annotations

import base64
import binascii
import hmac
import json
import re
import secrets
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from pydantic import SecretStr

_VERSION = b"IDC\x01"
_NONCE_BYTES = 12
_TOKEN_BYTES = 87
_ENVELOPE_BYTES = len(_VERSION) + _NONCE_BYTES + _TOKEN_BYTES + 16
_KEY_ID = re.compile(r"[A-Za-z0-9_-]{1,64}", re.ASCII)
_TOKEN_PART = re.compile(r"[A-Za-z0-9_-]{43}", re.ASCII)
_ERROR = "invalid delivery credential"


class CredentialError(ValueError):
    """A safe failure that never includes input or cryptographic diagnostics."""

    def __init__(self) -> None:
        super().__init__(_ERROR)


@dataclass(frozen=True, slots=True)
class CredentialContext:
    """Bind an envelope to one tenant, invitation, delivery, expiry and key."""

    organization_id: UUID
    invite_id: UUID
    delivery_id: UUID
    expires_at: datetime
    key_id: str


class LocalCredentialCipher:
    """Encrypt transient delivery tokens using a separate AES-256-GCM key."""

    __slots__ = ("_cipher", "_key_id")

    def __init__(self, key: SecretStr, key_id: str, forbidden_keys: tuple[str, ...]) -> None:
        try:
            if not isinstance(key, SecretStr) or not _valid_key_id(key_id):
                raise CredentialError()
            encoded = key.get_secret_value()
            if len(encoded) != 44:
                raise CredentialError()
            material = base64.b64decode(encoded, altchars=b"-_", validate=True)
            if len(material) != 32 or base64.urlsafe_b64encode(material).decode() != encoded:
                raise CredentialError()
            if not isinstance(forbidden_keys, tuple):
                raise CredentialError()
            for forbidden in forbidden_keys:
                if not isinstance(forbidden, str) or not forbidden or len(forbidden) > 4096:
                    raise CredentialError()
                representations = [forbidden.encode()]
                with suppress(ValueError, binascii.Error):
                    representations.append(
                        base64.b64decode(
                            forbidden + "=" * (-len(forbidden) % 4),
                            altchars=b"-_",
                            validate=True,
                        )
                    )
                if any(
                    hmac.compare_digest(candidate, material)
                    or hmac.compare_digest(candidate, encoded.encode())
                    for candidate in representations
                ):
                    raise CredentialError()
            self._cipher = AESGCM(material)
            self._key_id = key_id
            return
        except (ValueError, TypeError, UnicodeError, OverflowError):
            pass
        raise CredentialError()

    def encrypt(self, raw_token: str, context: CredentialContext) -> bytes:
        """Seal a canonical invite token with a fresh 96-bit random nonce."""

        try:
            aad = self._aad(context, datetime.now(UTC))
            plaintext = _token_bytes(raw_token)
            nonce = secrets.token_bytes(_NONCE_BYTES)
            return _VERSION + nonce + self._cipher.encrypt(nonce, plaintext, aad)
        except (ValueError, TypeError, UnicodeError, OverflowError):
            pass
        raise CredentialError()

    def decrypt(self, ciphertext: bytes, context: CredentialContext, *, now: datetime) -> str:
        """Open only an intact, correctly bound and unexpired envelope."""

        try:
            aad = self._aad(context, now)
            if (
                not isinstance(ciphertext, bytes)
                or len(ciphertext) != _ENVELOPE_BYTES
                or not ciphertext.startswith(_VERSION)
            ):
                raise CredentialError()
            boundary = len(_VERSION) + _NONCE_BYTES
            plaintext = self._cipher.decrypt(
                ciphertext[len(_VERSION) : boundary], ciphertext[boundary:], aad
            )
            token = plaintext.decode("ascii")
            _token_bytes(token)
            return token
        except (InvalidTag, ValueError, TypeError, UnicodeError, OverflowError):
            pass
        raise CredentialError()

    def _aad(self, context: CredentialContext, now: datetime) -> bytes:
        if not isinstance(context, CredentialContext):
            raise CredentialError()
        if not all(
            isinstance(identifier, UUID)
            for identifier in (context.organization_id, context.invite_id, context.delivery_id)
        ):
            raise CredentialError()
        if not _valid_key_id(context.key_id) or context.key_id != self._key_id:
            raise CredentialError()
        if not _utc(context.expires_at) or not _utc(now) or context.expires_at <= now:
            raise CredentialError()
        return json.dumps(
            [
                "iopsych-local-delivery-credential-v1",
                str(context.organization_id),
                str(context.invite_id),
                str(context.delivery_id),
                context.expires_at.isoformat(timespec="microseconds"),
                context.key_id,
            ],
            ensure_ascii=True,
            separators=(",", ":"),
        ).encode("ascii")


def _valid_key_id(value: str) -> bool:
    return isinstance(value, str) and _KEY_ID.fullmatch(value) is not None


def _utc(value: datetime) -> bool:
    return isinstance(value, datetime) and value.utcoffset() == timedelta(0)


def _token_bytes(value: str) -> bytes:
    if not isinstance(value, str) or len(value) != _TOKEN_BYTES:
        raise CredentialError()
    parts = value.split(".")
    if len(parts) != 2:
        raise CredentialError()
    for part in parts:
        if _TOKEN_PART.fullmatch(part) is None:
            raise CredentialError()
        decoded = base64.b64decode(part + "=", altchars=b"-_", validate=True)
        if len(decoded) != 32 or base64.urlsafe_b64encode(decoded).rstrip(b"=").decode() != part:
            raise CredentialError()
    return value.encode("ascii")
