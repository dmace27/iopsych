# 8A local invitation capture slice

Date: 2026-11-04. Base: `c20b3ed`. Branch: `AbhiNutakki/iopsych-local-delivery`.
This report belongs to the scoped implementation commit containing it; obtain its
revision with `git log -1 --format=%H -- apps/api/app/invitations/local_delivery.py`.
**Local adapter slice complete; full package 8A remains pending.**

## Changes and integration

- Added `LocalSmtpInvitationDelivery`, structurally compatible with the existing
  `InvitationDeliveryAdapter.send(InvitationEmail) -> None` interface.
- Explicit `enabled=True` construction is required. Immutable configuration accepts
  native numeric loopback only (IPv4 loopback or IPv6 `::1`), rejecting hostnames,
  scoped/mapped IPv6, URLs and ambiguous IPv4 notation before opening a connection.
- Only bare ASCII recipients beneath reserved `.test` / `.invalid` domains are
  accepted; the sender is fixed to `invitations@iopsych.invalid`. No credentials,
  authentication, debug logging, automatic retries or environment configuration.
- Multipart plain-text/HTML content is preserved. Socket timeout defaults to three
  seconds and must be finite, positive and at most ten seconds. This is a per-I/O
  timeout, not a total conversation deadline against a malicious slow-drip peer.
- Header injection, SMTP rejection, timeout and connection failures become a static
  `InvitationDeliveryError`; provider exception context is discarded. Teardown
  does not turn confirmed DATA acceptance into failure. No message content is logged.
- No migrations, shared contracts, service, router, main, configuration, dependencies
  or progress ledger were changed. This is not enabled in the default application.

Explicit injection by the runtime owner can use:

```python
from app.invitations.local_delivery import LocalSmtpInvitationDelivery

capture = LocalSmtpInvitationDelivery(enabled=True, host="127.0.0.1", port=1139)
# Pass capture to the existing invitation_delivery argument of create_app.
```

The sink must be operator-controlled with forwarding/relay disabled. Numeric
loopback constrains the destination but cannot prove the listening program is
Mailpit or inspect its forwarding configuration. Mailpit intentionally holds the
synthetic message body, including any synthetic invitation link; keep its UI
loopback-only and destroy its disposable data after use. Do not enable this adapter
for real recipients or hosted production. Container service names are intentionally
rejected; container deployments would need a separately reviewed local topology.

## Verification evidence

Python 3.12.16, pytest 9.1.1; existing installed dependencies only. From `apps/api`:

```sh
IOPSYCH_TEST_LOCAL_MAILPIT=1 ../../.venv/bin/pytest tests/test_local_invitation_delivery.py -o addopts='' --cov=app.invitations.local_delivery --cov-report=term-missing --cov-fail-under=100
../../.venv/bin/mypy app/invitations/local_delivery.py
```

Result: **48 passed, zero skipped; 100% line/branch coverage** of the new module
(52 statements, 14 branches); mypy passed. The global coverage target was replaced
with an explicit slice-only target; this is not evidence of a full API suite run.
From the repository root, both commands passed:

```sh
.venv/bin/ruff check apps/api/app/invitations/local_delivery.py apps/api/tests/test_local_invitation_delivery.py
.venv/bin/ruff format --check apps/api/app/invitations/local_delivery.py apps/api/tests/test_local_invitation_delivery.py
```

Tests include opt-in refusal, endpoint validation, real-recipient/header rejection,
rendered bodies/envelope, no credentials/debug logging, safe errors at connect/send,
ambiguous acceptance without retry, and teardown failure after acceptance.
The actual Mailpit test checks the captured recipient, subject, plain text and HTML
through its HTTP API, with HTTP environment proxies disabled. It is skipped unless
`IOPSYCH_TEST_LOCAL_MAILPIT=1` is explicitly provided.

Isolated Compose project `iopsych-8a-local-capture` used the already available image
`axllent/mailpit:v1.27.10`, no volume, credentials or relay configuration, and only
`127.0.0.1:1139:1025` / `127.0.0.1:8139:8025`. Reproduction configuration:

```yaml
services:
  mailpit:
    image: axllent/mailpit:v1.27.10
    ports:
      - '127.0.0.1:1139:1025'
      - '127.0.0.1:8139:8025'
    networks: [capture]
networks:
  capture:
    driver: bridge
```

Commands used: `docker compose -p iopsych-8a-local-capture -f /tmp/iopsych-8a-local-capture/compose.yaml up -d`
and the matching `down` after validation. No other projects or databases were
modified. No external mail was sent. Ports 3000/8000/8001 and reserved application/
database ports were untouched.

Initial checks found that Python accepts IPv4-mapped loopback, which is now
explicitly rejected. The first Mailpit attempt used an internal Docker network;
Docker did not expose its published ports and the integration check failed with
connection refused. Recreating only this project on a bridge network with explicit
loopback bindings resolved it; the final 48-test run above passed.

## Recommended recovery contract (proposal, not implemented or approved)

1. Require tenant-scoped issuance idempotency: a unique `(organization, key)` plus
   canonical request fingerprint. Repeat identical requests returns the same invite
   identifier/status without another send; changed payload conflicts. Bound key
   retention and authorization. Do not return raw links/tokens.
2. Atomically commit the invitation, pinned assignment, issuance audit and delivery
   intent before external delivery. Workers claim intents using bounded leases and
   stable delivery attempt identifiers; crash recovery must not create new invites.
3. If delivery intent needs a token, require a separately approved encrypted
   credential envelope with key separation, restricted worker-only decryption,
   explicit expiry no later than invitation expiry, deletion after terminal status,
   backup/deletion handling and no plaintext logging. A plain outbox token is not
   acceptable. This requires coordinator-owned schema/security design.
4. Separate `pending`, `sending`, `accepted`, `failed` and `unknown` delivery states
   from candidate lifecycle state. A lost acceptance response is `unknown`, not a
   safe retry. Reconcile through a chosen provider's stable idempotency/status API
   before bounded retries; SMTP alone cannot promise exactly-once delivery.
5. Revocation cancels unsent intents; reissue must atomically revoke the old invite
   and create a fresh assignment/token under an authorized new request. A racing
   old delivery may arrive but its link must remain revoked. Authenticated,
   deduplicated provider events may update bounce/delivery metadata without
   changing consent or assessment history.
6. Verify duplicate requests, audit/commit failure before send, worker crashes,
   acceptance-response loss, revoke/send races, retry exhaustion and encrypted
   credential expiry/deletion using synthetic data. Record no candidate content,
   email address or token in operational error metadata.

Full 8A issuance idempotency, durable outbox/recovery, tenant discovery, lifecycle
integration, provider selection/configuration/webhooks and controlled staging
mailbox-to-consent evidence remain open. This adapter provides neither provider,
scientific, product nor real-participant approval. Next eligible integration is
coordinator-owned explicit local factory injection, followed by the approved 8A
recovery/schema work after dependency and decision gates are satisfied.
