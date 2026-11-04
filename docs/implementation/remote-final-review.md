# Remote reconciliation final focused review

Reviewed 2026-11-04: merge checkpoint `266be89` through `0b7a569`, using
`266be89^1` as the integration-side baseline, then inspected current committed
remote lead `ad062064c738255d1ef1357683abcff59a763028`. The latter already contains
`22eeae1`; the anticipated merge is no longer pending at this checkpoint.
This is a focused review, not combined-release acceptance.

Read applicable web AGENTS, current progress and remote-migration-review.
Live own-terminal screen reads `GPT-6-Astra medium` without Fast; no toggle was
used. Application/code worktree reads only; no other worker private files read.

## Blocking finding: provider downgrade loses durable evidence

**P1**, `apps/api/alembic/versions/20261104_0012_provider_invitation_delivery.py`,
`downgrade()`, present at both `0b7a569` and `ad06206`:

- The guard counts only queued/retrying rows, then drops the event and delivery
  tables. Sent, delivered, failed, bounced, complained, reissue-required and
  cancelled rows therefore lose permanent issuance request tombstones; webhook
  event IDs and linkage also disappear. Re-upgrading recreates empty tables and
  permits an old request key to create another invitation.
- There is no lock before the count. Another transaction can commit a queued
  insert between the count and DROP acquiring its lock, and that credential-bearing
  row is discarded. DROP's own lock does not make the earlier predicate atomic.
- Minimal fix: acquire PostgreSQL ACCESS EXCLUSIVE locks on both provider tables
  before reading either, reject downgrade if either has any rows, then drop only
  verified-empty tables. Follow 0010/0011 lock-before-check practice and retain a
  fail-closed supported-dialect policy. Prefer compatible application rollback
  while retaining populated schema.

Sent immediately to lead `ctx_9a9c76cc5c41` (`msg_a924d963436d`) and coordinator
(`msg_be6e781dd91e`). A mock-only execution of the committed downgrade with a zero
pending count confirmed both drop calls, no connection execute/lock, and the
status-filtered predicate. This proves control flow; it is not a PostgreSQL race
rehearsal. Fix and populated/racing rollback checks remain required.

## Preservation findings

| Boundary | Evidence and conclusion |
| --- | --- |
| Canonical schema | 0012 descends from frozen notice0011, adds provider-prefixed delivery/event tables and event FK, leaving local invitation_deliveries separate. Earlier integration migration bodies are unchanged in the reviewed delta. This does not bridge remote0008/0009. |
| Assignment and notice | Existing immutable assignment model trigger remains; 0011 restores it after SQLite batch work and separately protects notice evidence, including unknown decided history. Notice downgrade locks both evidence tables and rejects populated evidence. No assignment rewrite was introduced to generate v2 reports. |
| Accounts | Existing account service is unchanged: tenant then actor/target locks, refreshed active/admin actor, strict expected_version, last-admin guard, no-op behavior and version increment remain. Provider PATCH delegates to it; provisioning takes the same tenant lock and reloads the actor. Subject authentication retains global-subject lookup, active-state check and optional HMAC tenant constraint. |
| Privacy and cancellation | Anonymization refreshes/locks the invite and calls both local and provider cancellation before redacting email/token. Reissue/revoke, consent and expiry paths also call both cancellation helpers. Provider workers lock invite before delivery, matching cancellation ordering. Database race behavior was not rerun. |
| Delivery uncertainty | Local worker/recovery code is unchanged and still refuses uncertain resend. Provider retry is a different contract: frozen encrypted payload, stable invite/delivery ID key, bounded 23-hour retry deadline, terminal payload erasure; never reinterpret local uncertain as provider retrying. Webhooks retain event dedupe and avoid reviving cancelled/reissue-required rows. |
| Login | Web default uses Auth0; synthetic local access remains explicitly development/loopback gated, with a separate local exchange. Arbitrary token login is opt-in. API provider default remains HMAC, so actual Auth0 deployment must explicitly select AUTH_PROVIDER=auth0; configured Auth0 has no HMAC fallback. No real provider verification was attempted. |
| v1/v2 | Registry retains both readers/matchers; historical v1 replay stays exact. New report generation explicitly selects v2 without mutating frozen assignment JSON, and trace checks reject algorithm/target tampering. Eight direct pure cases passed below. |

The preservation statements above are bounded code-review findings, not fresh
proof of SQL concurrency, production provider behavior or complete UI acceptance.
No additional blocking regression was established in these inspected paths.

## Check receipt and remaining gates

Used existing `.venv/bin/python`, with bytecode disabled and PYTHONPATH pointing
only to lead application/shared code. Directly invoked the pure functions from
`test_semantics_compatibility.py`: one exact v1 replay/reader case, four v2 trace
cases (complete/skipped/two-skipped/all-skipped), and three tamper cases
(1.0.0/2.0.0/99.0.0). **8 passed**, no pytest fixtures or database state. The
mock-only migration reproduction also passed its assertions confirming the defect.
No install, full suite, database, listener, credentials or hosted calls occurred.
Documentation checked with `git diff --check`.

Full remote-head upgrade remains blocked pending preserved remote history and an
explicit validated bridge with populated fixtures, rollback/evidence and retry
proof. A fresh PostgreSQL integration-head test cannot satisfy that gate. The
0012 downgrade fix must be reviewed at its actual commit. Coordinator-owned
combined regression, browser checks and real Auth0/Resend/hosted approval remain
separate; this report grants none of those approvals.
