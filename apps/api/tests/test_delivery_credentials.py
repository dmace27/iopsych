"""Synthetic authenticated-encryption and fail-closed credential tests."""

import base64
from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from pydantic import SecretStr

from app.invitations.credentials import CredentialContext, CredentialError, LocalCredentialCipher
from app.invitations.tokens import InviteTokenCodec

KEY_BYTES = bytes(range(32))
KEY = base64.urlsafe_b64encode(KEY_BYTES).decode()
NOW = datetime.now(UTC)
CONTEXT = CredentialContext(
    organization_id=UUID(int=1),
    invite_id=UUID(int=2),
    delivery_id=UUID(int=3),
    expires_at=NOW + timedelta(days=1),
    key_id="synthetic-v1",
)
TOKEN = InviteTokenCodec("synthetic-invite-signing-material-only").generate().raw_token


def invalid_fields(**values: Any) -> dict[str, Any]:
    return values


def cipher() -> LocalCredentialCipher:
    return LocalCredentialCipher(SecretStr(KEY), CONTEXT.key_id, ("synthetic-distinct-secret",))


def assert_safe(error: pytest.ExceptionInfo[CredentialError]) -> None:
    assert str(error.value) == "invalid delivery credential"
    assert error.value.__cause__ is None
    assert error.value.__context__ is None
    assert KEY not in repr(error.value)
    assert TOKEN not in repr(error.value)


def test_round_trip_random_nonce_and_no_secret_repr() -> None:
    instance = cipher()
    first = instance.encrypt(TOKEN, CONTEXT)
    second = instance.encrypt(TOKEN, CONTEXT)
    assert len(first) == 119
    assert first != second
    assert first[4:16] != second[4:16]
    assert TOKEN.encode() not in first
    assert KEY not in repr(instance)
    assert repr(KEY_BYTES) not in repr(instance)
    assert instance.decrypt(first, CONTEXT, now=NOW) == TOKEN
    assert instance.decrypt(second, CONTEXT, now=NOW) == TOKEN


@pytest.mark.parametrize("index", range(119))
def test_every_envelope_byte_is_authenticated(index: int) -> None:
    instance = cipher()
    envelope = bytearray(instance.encrypt(TOKEN, CONTEXT))
    envelope[index] ^= 1
    with pytest.raises(CredentialError) as error:
        instance.decrypt(bytes(envelope), CONTEXT, now=NOW)
    assert_safe(error)


@pytest.mark.parametrize(
    "field", ["organization_id", "invite_id", "delivery_id", "expires_at", "key_id"]
)
def test_context_substitution_fails(field: str) -> None:
    instance = cipher()
    replacement: Any = UUID(int=99)
    if field == "expires_at":
        replacement = CONTEXT.expires_at + timedelta(microseconds=1)
    if field == "key_id":
        replacement = "synthetic-v2"
    with pytest.raises(CredentialError) as error:
        instance.decrypt(
            instance.encrypt(TOKEN, CONTEXT), replace(CONTEXT, **{field: replacement}), now=NOW
        )
    assert_safe(error)


def test_different_encryption_key_fails() -> None:
    other = LocalCredentialCipher(
        SecretStr(base64.urlsafe_b64encode(bytes(reversed(KEY_BYTES))).decode()),
        CONTEXT.key_id,
        (),
    )
    with pytest.raises(CredentialError) as error:
        other.decrypt(cipher().encrypt(TOKEN, CONTEXT), CONTEXT, now=NOW)
    assert_safe(error)


@pytest.mark.parametrize(
    "value", [b"", b"x" * 118, b"x" * 120, b"x" * 10000, None, "x" * 119, bytearray(119)]
)
def test_malformed_envelopes(value: Any) -> None:
    with pytest.raises(CredentialError) as error:
        cipher().decrypt(value, CONTEXT, now=NOW)
    assert_safe(error)


@pytest.mark.parametrize(
    "value",
    [
        "",
        "a" * 10000,
        "a" * 87,
        "a" * 43 + "." + "a" * 43,
        "é" * 87,
        "=" * 43 + "." + "A" * 43,
        None,
        b"x",
    ],
)
def test_invalid_plaintext(value: Any) -> None:
    with pytest.raises(CredentialError) as error:
        cipher().encrypt(value, CONTEXT)
    assert_safe(error)


@pytest.mark.parametrize(
    "value",
    [
        "",
        "x" * 43,
        "x" * 44,
        "!" * 44,
        "é" * 44,
        base64.urlsafe_b64encode(bytes(31)).decode(),
        KEY[:-2] + "9=",
        KEY.rstrip("="),
        "x" * 10000,
    ],
)
def test_invalid_key_encoding(value: str) -> None:
    with pytest.raises(CredentialError) as error:
        LocalCredentialCipher(SecretStr(value), CONTEXT.key_id, ())
    assert_safe(error)


@pytest.mark.parametrize("value", ["", "bad id", "é", "x" * 65, None, "a\n"])
def test_invalid_key_id(value: Any) -> None:
    with pytest.raises(CredentialError) as error:
        LocalCredentialCipher(SecretStr(KEY), value, ())
    assert_safe(error)
    with pytest.raises(CredentialError):
        cipher().encrypt(TOKEN, replace(CONTEXT, key_id=value))


@pytest.mark.parametrize(
    "forbidden",
    [
        (KEY,),
        (KEY.rstrip("="),),
        (KEY_BYTES.decode(),),
        (base64.b64encode(KEY_BYTES).decode(),),
        (base64.b64encode(KEY.encode()).decode(),),
        (None,),
        ("",),
        ("x" * 4097,),
        [KEY],
    ],
)
def test_forbidden_key_reuse_and_invalid_configuration(forbidden: Any) -> None:
    with pytest.raises(CredentialError) as error:
        LocalCredentialCipher(SecretStr(KEY), CONTEXT.key_id, forbidden)
    assert_safe(error)


def test_urlsafe_and_standard_forbidden_encodings() -> None:
    material = b"\xfb" * 32
    with pytest.raises(CredentialError):
        LocalCredentialCipher(
            SecretStr(base64.urlsafe_b64encode(material).decode()),
            CONTEXT.key_id,
            (base64.b64encode(material).decode().rstrip("="),),
        )
    plain_key: Any = KEY
    with pytest.raises(CredentialError):
        LocalCredentialCipher(plain_key, CONTEXT.key_id, ())


@pytest.mark.parametrize(
    "now",
    [
        CONTEXT.expires_at,
        CONTEXT.expires_at + timedelta(seconds=1),
        NOW.replace(tzinfo=None),
        NOW.astimezone(timezone(timedelta(hours=1))),
        None,
    ],
)
def test_invalid_clock_or_expired(now: Any) -> None:
    instance = cipher()
    with pytest.raises(CredentialError) as error:
        instance.decrypt(instance.encrypt(TOKEN, CONTEXT), CONTEXT, now=now)
    assert_safe(error)


@pytest.mark.parametrize(
    "expiry",
    [
        NOW - timedelta(seconds=1),
        NOW.replace(tzinfo=None),
        NOW.astimezone(timezone(timedelta(hours=1))),
        None,
    ],
)
def test_invalid_expiry(expiry: Any) -> None:
    with pytest.raises(CredentialError) as error:
        cipher().encrypt(TOKEN, replace(CONTEXT, expires_at=expiry))
    assert_safe(error)


@pytest.mark.parametrize(
    "context",
    [
        None,
        replace(CONTEXT, **invalid_fields(organization_id="1")),
        replace(CONTEXT, **invalid_fields(invite_id=None)),
        replace(CONTEXT, **invalid_fields(delivery_id=3)),
    ],
)
def test_invalid_context(context: Any) -> None:
    with pytest.raises(CredentialError) as error:
        cipher().encrypt(TOKEN, context)
    assert_safe(error)


@pytest.mark.parametrize("plaintext", [b"x" * 87, b"\xff" * 87])
def test_authenticated_but_invalid_plaintext_fails(plaintext: bytes) -> None:
    instance = cipher()
    nonce = bytes(12)
    envelope = (
        b"IDC\x01"
        + nonce
        + AESGCM(KEY_BYTES).encrypt(nonce, plaintext, instance._aad(CONTEXT, NOW))
    )
    with pytest.raises(CredentialError) as error:
        instance.decrypt(envelope, CONTEXT, now=NOW)
    assert_safe(error)
