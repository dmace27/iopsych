# Account and delivery integration review

Reviewed 2026-11-04 at application revision `b704965`. Worktree base is
`37da365`, whose only change after that revision is the coordination ledger.
This is a read-only application review; only this report changes.

Read `apps/web/AGENTS.md`, the accelerated schedule in
`final-implementation-plan.md`, and the current progress ledger. Inherited the
dispatch's verified Fast setting without toggling it. No application tests,
installers, servers, database connections, mail sends, or full suites were run.
Setup completion was not established, so no test run was attempted. Findings
below are source traces, not independently reproduced runtime results or an
approval of release readiness.

## Findings and acceptance gaps

### 1. Terminal delivery failure is invisible in invitation discovery (medium)

`apps/api/app/invitations/worker.py:92` changes delivery rows during cleanup;
`_complete` changes the invitation only when a sending job becomes sent. An
expired queued credential or an uncertain send therefore leaves its invitation
in `pending_delivery`. `apps/api/app/invitations/schemas.py:44` exposes invitation
status but no delivery state, and discovery serializes that representation.
The invitation workspace labels it “Pending delivery” indefinitely.

Concrete trace: issue a queued invitation, let its 15-minute credential expire,
run cleanup, then refresh invitation history. The queue is terminal `expired`
with no credential, but the API still returns `pending_delivery` and no
machine-readable indication that delivery cannot proceed. Likewise, an SMTP
exception produces terminal `uncertain` while the invitation remains pending.
Same-key replay returns `invitation_reissue_required`, but discovery cannot
explain that condition before the recruiter attempts issuance again.

The UI explicitly says it displays stored invitation status and excludes delivery
receipt; it does not falsely claim successful delivery. Nevertheless, actionable
failure/recovery acceptance remains incomplete. Agree an additive delivery-state
representation or equally clear recovery indication, and verify expired and
uncertain cases through the real UI. This was sent promptly to the coordinator;
queue and issuance owners retain implementation ownership.

### 2. Successful account no-op is rejected by the web client (low)

`apps/api/app/accounts/service.py:85` returns the unchanged account/version when
the requested role and activation already match storage. This is explicitly
asserted in `test_role_disable_reactivate_and_version` in
`apps/api/tests/test_accounts.py`. However,
`apps/web/lib/account-client.ts:84` rejects every response whose version is less
than **or equal to** `expected_version`.

Thus a valid `updateAccount(id, {expected_version: N, is_active: true})` against
an already-active account at version N gets HTTP 200 but throws
`invalid_api_response`. The current workspace normally prevents this case by
disabling unchanged role submission and toggling activation, so this is a client
contract inconsistency rather than a demonstrated ordinary-click failure or an
authorization bypass. Align the client with server no-op semantics and retain
strict ID/version checks, accepting equality only when requested fields match
the returned state. Account owners were notified; no account files changed.

### 3. Cancellation stops activation, not an already-claimed outbound send

`apps/api/app/invitations/worker.py:166` commits a claim containing recipient and
ciphertext, then decrypts/builds/sends outside the transaction. If revocation
commits after `_claim` returns but before `adapter.send`, the in-memory claim can
still send to the original address. Deleting database ciphertext cannot recall
that copy. `_complete` respects terminal cancellation and does not reactivate the
revoked invitation, so this trace does **not** establish a usable revoked link.

Record this boundary in operational/privacy acceptance and exercise a paused
claim → revoke → resume-send interleaving. The existing source includes concurrent
worker and privacy-erasure cases, but those are not evidence of this precise
interleaving. A pre-send reread alone cannot eliminate the external-send race.
Do not promise that revocation guarantees no later email; this is especially
relevant before extending the local-only queue to a real provider.

### 4. Expiry enforcement and physical credential removal have different gates

The cipher refuses expired credentials; staging caps their lifetime at 15 minutes.
Physical erasure requires `cleanup_deliveries`, revocation, or worker completion.
Source search of application/scripts/deployment finds cleanup called by worker
drain, with separate scheduling described in
`docs/implementation/report8a-local-recovery.md`, but no deployed scheduler here.
If nobody runs either path, expired ciphertext remains stored. The assessment
retention runner does not call queue cleanup and selects submitted assessments,
so pending invitations are not covered by that runner.

This is an explicit unattended lifecycle acceptance gap, not proof that expired
credentials authenticate. Verify key-independent cleanup scheduling, backlog
draining, failure alerting, and policy for invitation-only personal data before
claiming full lifecycle retention. Existing progress already keeps these broader
privacy/provider gates open.

## Security boundaries supported by the source

- Authentication verifies the bearer then loads tenant-scoped user state and
  rejects inactive users on each request. Token role claims do not override the
  stored role. Account mutation locks the organization, refreshes/locks the actor,
  rechecks active administrator status, then locks the tenant-scoped target.
  Self-change, stale versions, and last-active-administrator removal are guarded.
  Audit and access mutation use the same request transaction.
- Reactivation intentionally makes a still-valid old token usable again. The
  existing account test explicitly expects this. Account version is optimistic
  concurrency state, not a token revocation epoch; do not describe deactivation
  as permanent session invalidation. No new policy approval is inferred.
- Account discovery and cursor lookup are tenant-scoped. The browser proxy allows
  only account GET and UUID PATCH, obtains its bearer from the HTTP-only cookie,
  and applies the existing same-origin mutation guard. The account UI hides rows
  after 401/403 and requires refresh after uncertain mutations rather than retrying.
- Queue replay uses tenant-scoped idempotency digests, checks request equality and
  invitation ownership, and rejects revoked/expired/uncertain terminal replay.
  Staging checks the profile's owner; the worker checks ownership again. Encryption
  binds tenant, invitation, delivery, expiry and key ID, with a fresh nonce.
  Successful claim commit precedes send; uncertain outcomes never auto-retry.
- Privacy export and anonymization lock the assessment; export builds a deep
  response copy. Anonymization calls cancellation before replacing invitation
  email/token and revoking it. Worker completion and revocation lock invitation
  before delivery. These source checks do not substitute for PostgreSQL race tests.

## Migration and integration acceptance

Migration 0009 adds a separate queue without rewriting synchronous invitations.
Its downgrade refuses queued/sending rows, but dropping the table also drops
terminal idempotency history. A downgrade/upgrade is therefore not preservation
of replay protection: the same key can later be treated as new. Require an
explicit rollback/reissue procedure rather than implying dedupe survives it.

At the reviewed revision, migration 0010 defaults existing accounts active at
version 1 and drops both fields unconditionally on downgrade. Downgrading with
inactive accounts removes the enforcement state; this is the already-delegated
account-hardening rollback issue, not a new parallel implementation assignment.
Its fix and populated full-chain checks must be reviewed at their eventual commit.

At `b704965`, the browser proxy has invitation list/revoke routes but no issuance
POST route and does not forward `Idempotency-Key`. Those changes already belong
to the issuance UI/proxy workers. The synchronous delivery path still sends before
the request transaction commits; the opt-in local queue does not repair that
default or constitute production provider selection.

No cross-tenant account/queue bypass or stale-role escalation was established by
this review. No passing test counts are claimed. The coordinator still needs the
owned account/queue tests, issuance integration, actual browser failure/recovery
checks, migration evidence, and later combined checkpoint. Hosted, manual,
scientific, privacy-policy and real-participant approvals remain ungranted.

Coordinator acknowledgement at 23:12 UTC accepted findings 1 and 2 and assigned
separate delivery-state API/UI work and a requested-field-aware account client
fix. The queue reviewer was informed of the cancellation boundary. These are
engineering assignments, not evidence that fixes have landed or passed checks.
