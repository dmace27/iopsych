# 8A local delivery credentials

Implemented in the isolated `AbhiNutakki/iopsych-delivery-crypto` worktree from
`b7ae145`. This slice provides the frozen credential interface only; it does not
complete package 8A or authorize real candidate delivery.

## Interface and envelope

`CredentialContext(organization_id: UUID, invite_id: UUID, delivery_id: UUID,
expires_at: datetime, key_id: str)` is an immutable dataclass.
`LocalCredentialCipher(key: SecretStr, key_id: str,
forbidden_keys: tuple[str, ...])` exposes
`encrypt(raw_token: str, context: CredentialContext) -> bytes` and
`decrypt(ciphertext: bytes, context: CredentialContext, *, now: datetime) -> str`.
Failures use `CredentialError` with the fixed message `invalid delivery credential`
and no retained underlying exception context or cause.

The key must be canonical padded URL-safe base64 representing exactly 32 bytes.
The caller must supply every configured signing/authentication secret in
`forbidden_keys`. Key reuse is rejected against literal UTF-8 values and decoded
standard/URL-safe base64 forms, including unpadded forms. The cipher retains the
cryptography cipher object rather than the supplied `SecretStr`; its default
representation contains no key material. Key IDs are 1–64 ASCII letters, digits,
underscores or hyphens. Invalid forbidden-key configuration also fails closed.

Encryption uses installed `cryptography==50.0.2` AESGCM with a fresh random
12-byte nonce. The binary envelope is exactly 119 bytes: four-byte `IDC\x01`
version marker, nonce, and 87-byte ciphertext with a 16-byte GCM tag. Any other
size or version is rejected before decryption. Plaintext must match the existing
invite codec's two canonical unpadded base64url components of 32 bytes each,
separated by a dot. This cipher validates token shape, not the invite signature;
normal invite validation remains responsible for signature verification.

AAD is deterministic compact ASCII JSON containing a versioned domain separator,
all three UUIDs, the UTC expiry rendered to microsecond precision, and key ID.
Changing any field invalidates authentication. UUID objects are required;
naive and nonzero-offset timestamps are rejected rather than silently normalized.
Encryption requires expiry after the current UTC clock; decryption requires
expiry strictly after the supplied aware UTC `now`. Equality is expired. Preserve
expiry microseconds when persisting and reconstructing context. The service must
supply a trusted current clock rather than accepting caller-controlled `now`.

## Verification

All input and key material in tests is synthetic. No environment secrets,
database, network service, port, or mail provider was used.

Run from the child worktree, with coordinator virtualenv and explicit child imports:

```sh
PYTHONPATH="$PWD/apps/api:$PWD/packages/shared/python" /Users/abhiramnutakki/iopsych/.venv/bin/python -m pytest -c apps/api/pyproject.toml apps/api/tests/test_delivery_credentials.py --override-ini addopts='' --cov=app.invitations.credentials --cov-branch --cov-report=term-missing --cov-fail-under=100 -q
/Users/abhiramnutakki/iopsych/.venv/bin/ruff check apps/api/app/invitations/credentials.py apps/api/tests/test_delivery_credentials.py
PYTHONPATH="$PWD/apps/api:$PWD/packages/shared/python" /Users/abhiramnutakki/iopsych/.venv/bin/mypy --config-file apps/api/pyproject.toml --follow-imports=silent apps/api/app/invitations/credentials.py apps/api/tests/test_delivery_credentials.py
```

Results: **181 passed**, credential module **100% statement and branch coverage**,
Ruff passed, and strict mypy passed for both owned Python files. Tests include
round trips, nonce freshness, every envelope byte independently modified,
wrong tenant/invite/delivery/expiry/key ID/key material, malformed and oversized
inputs, canonical encoding, signing/auth key reuse, expired/invalid clocks,
authenticated invalid plaintext, and safe exception representations/chains.

## Integration ownership and remaining work

No migrations, dependency manifests, configuration, schema, runtime, or service
files changed. The coordinator owns integration, the cryptography dependency pin,
and any persistence migration. The delivery worker (`ctx_d834fe802560`) owns the
explicit local-only mode gate, key configuration wiring, trusted clock, access
controls, delivery recovery, and expiry/deletion lifecycle. These controls must
be integrated before storing delivery credentials. No automatic key rotation or
legacy-envelope compatibility is provided; the service must retain the matching
key while an unexpired envelope remains recoverable, or invalidate/reissue it.
Hosted-provider evidence and full 8A acceptance remain separate work.
