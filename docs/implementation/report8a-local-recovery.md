# 8A local synthetic durable recovery slice

Date: 2026-11-04. Branch: `AbhiNutakki/iopsych-delivery-recovery`.

This implements the coordinator-approved **local synthetic PostgreSQL opt-in**
from `report8a-durable-contract.md`. It does not complete package 8A. The existing
synchronous default still sends before its database/audit commit; operators must
not interpret this slice as fixing the default mode or approving a mail provider.

## Changes and integration order

- Policy/contract: `8026161`; 53 focused tests, 100% policy statement/branch coverage.
- Crypto dependency is coordinator-owned (`cryptography==50.0.2`, `60cacf6`).
  Crypto implementation is separate owner commit `3c41b3b`, consumed here as
  `16038b7`; see `8a-credentials.md` for its verification.
- Schema: `4e73992`, migration `20261104_0009` parent `20261104_0008`, new
  `invitation_deliveries`, no backfill or modification of existing invitations.
  Downgrade refuses while queued/sending credentials remain. Cancel/expire first;
  dropping the table intentionally loses its historical idempotency tombstones.
- Runtime: commit containing this report, obtainable with
  `git log -1 --format=%H -- docs/implementation/report8a-local-recovery.md`.
  Coordinator integrates runtime after schema and crypto/dependency. No discovery
  code or response schemas were changed, and no provider was configured.

Issuance requires development authentication settings, synthetic definitions,
loopback candidate URL, a separate canonical base64 256-bit encryption key and
PostgreSQL. `INVITE_LOCAL_QUEUE_ENABLED` defaults false. Key ID is 1–64 ASCII
letters/digits/underscore/hyphen. Both JWT and invite-signing keys must be configured
and differ from the encryption material, including equivalent encoded forms.
Keys remain operator-injected secrets and must not be written to reports or Git.
The local shared symmetric key is explicitly **not production process isolation**.

Opt-in POST keeps the existing 201 response shape, initially `pending_delivery`.
It requires a 16–128 visible-ASCII `Idempotency-Key` header. Same tenant/key/payload
replays the invite before new assignment generation; changed payload is 409.
Role/profile authorization is checked before replay. Concurrent duplicates use a
unique key plus savepoint, preserving unrelated outer request/audit work.
Unresolved sending/uncertain attempts for that role and recipient must be revoked
before replacement issuance. Dedupe rows are retained; terminal keys are not recycled.

The worker commits `sending` and its audit before decrypting or calling SMTP.
Success activates the invitation, deletes ciphertext/key ID and appends audit in
one transaction. SMTP errors or invalid/lost keys become `uncertain`, clear the
credential, and never retry automatically. A completion/audit commit failure leaves
`sending`; cleanup after two minutes converts it to `uncertain`, never resends.
The two-minute grace is not a claim that SMTP has a total wall-clock timeout.
A slow original send can still finish, but cannot reactivate a recovered terminal
row. A post-claim revocation can race email arrival; its link remains unusable.

Credential expiry is min(invite expiry, issuance + 15 minutes), authenticated by
the cipher. Cleanup is bounded to at most 100 rows per call and needs no encryption
key. Revocation and privacy anonymization clear credentials in their own audited
transaction, locking invite then delivery consistently with worker completion.
Lost encryption keys do not block API revocation. Jobs never contain rendered
emails or raw tokens; responses/audit metadata contain no delivery credentials.

## Local operation

Use only a fresh isolated local PostgreSQL database (this task used 5586 and
`iopsych_delivery`), migrations through 0009, an operator-controlled non-relaying
loopback SMTP sink, and synthetic `.test`/`.invalid` recipients. Configure:

- `AUTH_ENVIRONMENT=development`
- `INVITE_LOCAL_QUEUE_ENABLED=true`
- `INVITE_ALLOW_SYNTHETIC_DEFINITIONS=true`
- `INVITE_CANDIDATE_BASE_URL=http://127.0.0.1:3146/candidate/invites`
- `INVITE_LOCAL_QUEUE_KEY_ID=local-v1`
- Inject `INVITE_LOCAL_QUEUE_KEY`, `AUTH_JWT_SECRET` and
  `INVITE_TOKEN_SIGNING_SECRET` separately through the local process environment.

The worker is an explicit library entry point, not an application startup task or
managed scheduler. With those settings and the isolated `DATABASE_URL` configured,
run from `apps/api` using the project's interpreter:

```python
from app.auth.config import AuthenticationSettings
from app.database.session import create_database_engine, create_session_factory
from app.invitations.config import InvitationSettings
from app.invitations.local_delivery import LocalSmtpInvitationDelivery
from app.invitations.worker import LocalDeliveryWorker, cleanup_deliveries

engine = create_database_engine()
factory = create_session_factory(engine)
try:
    worker = LocalDeliveryWorker(
        factory, InvitationSettings(), AuthenticationSettings(),
        LocalSmtpInvitationDelivery(enabled=True, host="127.0.0.1", port=1139),
    )
    worker.drain(limit=25)
finally:
    engine.dispose()
```

Schedule key-independent `cleanup_deliveries(factory, limit=100)` separately even
if no worker can decrypt, repeating bounded calls as needed. Live ciphertext
expiry enforcement prevents sending after TTL, but actual deletion requires this
cleanup to run. This task does not provision a scheduler. Do not print messages,
credentials or captured invite links. Revoke uncertain invites through the existing
endpoint, then issue a replacement with a fresh key. No automatic resend endpoint
or production delivery-status API is introduced.

## Evidence and limits

Tests use disposable schemas inside owned tmpfs container
`ab3bd993599266d4d3cb2503a35f959b418831dd7cdff133d61dea509a9449c0`,
name `iopsych-delivery-task1324`, bound only to `127.0.0.1:5586`. No existing database
was reset and protected ports were untouched. SMTP was patched at the local adapter
boundary for transaction tests; no real mail or external provider was used.

The focused matrix covers populated 0008→0009 upgrade, downgrade guard, concurrent
issuance, outer transaction preservation, concurrent workers, durable claim visibility,
claim/completion commit failures, request audit rollback, revoke-during-send, exact
response compatibility/replay, tamper rejection, tenant consistency, bounded cleanup,
privacy erasure, wrong configuration and non-PostgreSQL rejection. SQLite testing
exposed outermost SAVEPOINT release before request rollback, so the queue fails
closed on SQLite rather than claiming equivalent transactional behavior.

The broad API run before the final keyless-revoke test produced 816 passed,
19 failed, 11 skipped in 17.10 seconds. All 19 failures were telemetry capture
assertions after migration logging reconfiguration; coordinator has a separate
hermetic-logging worker. No telemetry edits were made here. Unrelated opt-in
PostgreSQL/Mailpit tests remained skipped. This is not a clean full-suite claim.
Focused final results and static checks are recorded in the dispatch summary.

Remaining release gates: coordinator integration/full CI and 100% aggregate coverage,
managed cleanup scheduling, staging mailbox/candidate browser rehearsal, production
key-service/process isolation, encrypted backup/key retirement policy, transactional
provider selection/configuration, bounce/webhook handling, delivery status UX and
all product/privacy/scientific approvals. Local role separation alone does not
supply production decryption isolation, and deleting live ciphertext does not erase
historical backups. No provider, purchase, deployment or real-pilot approval is implied.

Final validation details: the six-file focused regression command was
`pytest tests/test_delivery_queue.py tests/test_invitations.py tests/test_privacy.py
 tests/test_database_migrations.py tests/test_delivery_credentials.py
 tests/test_invitation_recovery.py -o addopts='' --cov=app.invitations.queue
 --cov=app.invitations.worker --cov-report=term-missing -q` (run from `apps/api`
with child `PYTHONPATH` and the isolated `TEST_DELIVERY_POSTGRES_URL`). It passed
285 tests before final audit-owner hardening; final queue tests were rerun after
that change. Queue/worker combined branch-inclusive coverage is 96%, not 100%;
remaining misses are defensive missing-row/owner paths and bounded-loop branches.
Ruff and strict mypy passed for the changed runtime and focused tests. The broader
telemetry fixture fixes are coordinator commits `ba2759a` and `b457baf`, not part of
this child branch; the coordinator requested no further full-suite run here.

Final queue rerun: **31 passed** in 6.44 seconds after audit-owner hardening and
keyless API revocation checks. The owned tmpfs PostgreSQL container identified
above was removed after verification; no persistent database volume was created.
