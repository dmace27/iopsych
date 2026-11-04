# 8A durable invitation delivery engineering contract

Date: 2026-11-04. Base: `19e5844`. Proposal, not an approved migration or API change.

## Existing behavior and compatibility

`InternalInvitationService.create` sends before the audit middleware commits.
Successful delivery followed by database/audit failure can therefore email a
nonexistent invite. SMTP timeout can mean acceptance, and blind retry duplicates
mail. Keep the existing synchronous mode unchanged until opt-in recovery passes
the integration gates below. Discovery and response schemas remain unchanged.

## Minimal proposed contract requiring coordinator approval

One new table `invitation_deliveries`, with UUID primary key, `organization_id`
and unique `invite_id` foreign keys (RESTRICT); `idempotency_digest` CHAR(64),
`request_digest` CHAR(64), `state` VARCHAR(16), `attempt_count` INTEGER default 0,
nullable `credential_ciphertext` binary, nullable `credential_key_id` VARCHAR(80),
`credential_expires_at`, `created_at`, `updated_at`, and nullable `attempt_started_at`
UTC timestamps. Unique `(organization_id, idempotency_digest)`; index
`(state, credential_expires_at)`. Allowed states: queued, sending, sent, uncertain,
cancelled, expired. Nonnegative attempt count; ciphertext/key ID required only
for queued/sending; both NULL for terminal states. No email body or raw credential
column. Coordinator allocates migration revision and approves exact constraints.

Opt-in issuance requires an `Idempotency-Key` header (opaque 16–128 printable ASCII
characters), returning existing 201 `InvitationResponse` with pending_delivery.
Same tenant/key and canonical request fingerprint returns the original invite;
changed payload returns 409. Canonical payload binds role ID, profile ID, normalized
validated email, explicit requested expiry (including omitted/default distinction),
and any future request fields. Hash both key and canonical request using SHA-256;
never log the header or email. Check authorization before replay, retain dedupe
row through invite retention, and refuse expired/cancelled-key reuse (new key for
explicit reissue). Unique constraint arbitrates concurrent requests; re-read after
rollback in a fresh transaction. Sync mode retains its present header behavior.

Atomically commit invite, encrypted credential, dedupe row and issuance audit;
no network send during request transaction. Worker claims queued row with PostgreSQL
row lock/SKIP LOCKED, verifies invite eligibility and expiry, writes sending plus
attempt count and attempt audit, and commits BEFORE calling local SMTP. A second
transaction atomically activates invite, marks sent, clears ciphertext/key ID and
writes completion audit. A crashed/stale sending attempt becomes uncertain and
clears credentials; no automatic retry. Any SMTP exception is conservatively
uncertain; no claims of exactly-once SMTP. Successful send then completion/audit
failure leaves sending, recoverable to uncertain, never queued. A pre-send claim
commit failure sends nothing. An initial issuance/audit failure sends nothing.
Do not hold a SQL transaction across SMTP. Revocation can race a committed send:
completion must lock invite and never reactivate revoked/expired/declined state.
Such a message can arrive but its link must be unusable.

Uncertain delivery requires explicit revoke then reissue with a new key. Old link
is invalidated before replacement is queued. Revoke/retention cancel queued work
and clear its ciphertext atomically. Hard credential TTL is min(invite expiry,
creation + 15 minutes); expired work is never decrypted or sent. Cleanup must run
even without successful sends. Sending recovery waits a bounded operational grace
period above local adapter timeout, then becomes uncertain (never resends).

## Encryption and dependencies

Declared runtime dependencies include SQLAlchemy, psycopg, Pydantic, FastAPI,
Alembic, uvicorn; no cryptography/PyNaCl declaration. The child `.venv` contains
neither cryptography/PyNaCl nor pytest/SQLAlchemy (`pip show`, 2026-11-04).
Coordinator alone owns dependency additions and installation. Proposed dependency:
`cryptography==50.0.2`, subject to coordinator dependency/security verification.
Its [PyPI release](https://pypi.org/project/cryptography/50.0.2/) lists Python 3.12
support; the [AEAD API](https://cryptography.io/en/latest/hazmat/primitives/aead/)
provides authenticated encryption and associated-data verification. No package was
installed or requirements changed by this worker.
Use AES-256-GCM with fresh 96-bit nonce and authenticated context binding format
version, tenant ID, invite ID, delivery ID, credential expiry and key ID. Store
version+nonce+ciphertext/tag only. Do not implement homemade encryption.

Dedicated encryption key must differ from signing/auth keys and be injected via
isolated secret/key store, never DB, repo, logs or ordinary config snapshots.
API issuer needs encryption permission; only delivery worker needs decryption;
production role isolation requires an external envelope/key service (a shared
symmetric key in both processes does NOT provide that isolation). Local synthetic
mode may use a separate ephemeral operator-injected key with explicit documented
local-only trust. Missing key/authentication failure fails closed without fallback
plaintext. Rotation retains old keys only until credential TTL/cleanup; key loss
requires revoke/reissue. Live-row deletion does not erase backups: encrypted
backups require isolated keys and bounded retention/retirement. Credentials and
rendered email must be excluded from repr, exceptions, traces and audit metadata.

## Bounded implementation and remaining gates

Implement a dependency-free recovery decision module and focused failure matrix
tests without touching service/models/migrations/dependencies or wiring runtime.
It will make expiry, terminal credential deletion and no-retry-after-claim rules
executable, but will not claim durable persistence or solve current send-before-
commit by itself. Exact schema/API, migration assignment, encryption dependency,
key isolation and runtime wiring remain coordinator gates.

After approval: test opt-in issuance/replay/concurrency and audit rollback against
isolated PG5586/iopsych_delivery; inject commit failures before/after SMTP, process
crash, expiry, revoke races, lost keys and decryption failures. Verify no plaintext
credential in storage/logs/API and preserve synchronous regression tests. Local
adapter only, no provider selection/configuration, real mail or external approvals.
Production delivery, webhook/bounce handling and real-pilot approval remain open.
