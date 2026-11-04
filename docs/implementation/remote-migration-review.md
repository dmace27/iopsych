# Remote migration compatibility review

Reviewed integration `b77567c` against remote `646201a`; application and migration
files were read only. Read the accelerated schedule and progress ledger and the
available web AGENTS guidance; no root/ancestor/docs AGENTS was found. This worker
ran in its isolated worktree; the live Orca screen showed `GPT-6-Astra medium fast`.
No database, provider, mail, deployment, or full test suite was used. This is a
design review, not a successful populated-upgrade receipt. Initial blocking
findings were sent to the coordinator for lead `ctx_9a9c76cc5c41` immediately.

## Blocking finding and existing DAG

The common migrations through `20260929_0007` are byte-identical between commits.
Full revision IDs differ; their numeric suffixes alone are not migration identity.

```text
20260929_0007
  +-- 20261103_0008 active users --> 20261103_0009 provider outbox [remote]
  +-- 20261104_0008 assignment --> 20261104_0009 local queue
                                  --> 20261104_0010 access [integration]
                                      --> 0011 notice [pending owner handoff]
```

An ordinary merge revision cannot repair these ancestors: either traversal order
tries to create `invitation_deliveries` twice and add `users.is_active` twice.
Do not renumber/reparent committed revisions, delete deployed remote history, or
stamp a remote database as integration head without performing and verifying the
missing schema/data work. Remote head is a supported *possible deployed schema*;
this review did not inspect a deployment or establish that one exists.

## Compatibility table

| Object | Integration | Remote | Required preservation |
| --- | --- | --- | --- |
| `users.is_active` | 0010, non-null true default | 0008, same intended default | Preserve false values; never blindly backfill true on an existing column |
| `users.version` | Non-null integer default 1, `ck_users_version_positive` | Absent | Add only where absent; never reset populated versions |
| `users.auth_subject` | Global `uq_users_auth_subject`, not null | Same common 0002 and model | Preserve globally, not tenant-scoped; no email-based identity remapping |
| Invite assignment | Nullable JSON plus immutable trigger; frozen v1 checksum backfill | Absent | Preserve populated and intentionally NULL values, frozen definition file and trigger |
| `invitation_deliveries` | Local binary credential envelope, digest request keys, six states | Provider text envelope, UUID request keys, nine statuses | Two distinct tables/models; do not reinterpret one as the other |
| Local constraints | Unique invite; unique `(organization_id,idempotency_digest)`; attempts >= 0; credentials iff queued/sending | Not present | Retain every check, unique, expiry index and FK |
| Provider constraints | Not present | Unique invite, `(organization_id,request_id)`, provider message ID; due index | Retain request tombstones and webhook linkage; preserve original IDs |
| `invitation_delivery_events` | Absent | Provider event ID PK, FK to remote delivery | Preserve deduplication rows and FK target through rename |
| Notice 0011 | Pending nullable snapshot and consent evidence; parent 0010 | Absent | Integrate exact owner revision after handoff; no fabricated historical evidence |

Both delivery enums use VARCHAR/check constraints, not PostgreSQL native enum
types: local `invitation_delivery_state` length 16 versus remote
`invitation_delivery_status` length 32. Their union is not a valid state machine.
Local states are queued/sending/sent/uncertain/cancelled/expired; provider states
are queued/retrying/sent/delivered/failed/bounced/complained/reissue_required/cancelled.
In particular, uncertain must never become retrying, and sent is not delivered.
Remote ciphertext is Text `encrypted_message`; local is binary ciphertext plus
key ID and expiry. There is no evidenced lossless ciphertext or request-key
conversion. `requested_by` cannot be invented for historic local rows.

## Concrete non-destructive convergence plan

Keep integration `invitation_deliveries` as the local queue and introduce
`provider_invitation_deliveries` for the remote outbox. The provider event FK must
reference that table. Use distinct ORM class names and route providers explicitly.
Keep each provider's uniqueness scopes and encryption format; cancel both stores
on privacy deletion/reissue. One issuance must select exactly one transport;
separate per-table invite uniqueness does not prevent a duplicate cross-store send.

The safest plan with unchanged historical migration bodies is an explicit,
reviewed remote-lineage import bridge, separate from normal Alembic traversal:

```text
fresh/common/integration heads --> unchanged integration chain --> 0011 --> C
remote 0008/0009 --> transactional bridge B --> verified C schema/version
```

`C` is a newly allocated integration descendant after the exact notice handoff;
it creates the provider table/events for normal integration upgrades. `B` is an
operational compatibility transaction, not a pretend Alembic merge edge. Preserve
the remote migration files in a separate explicitly selected legacy migration
location so default `head` stays unambiguous. The coordinator must approve this
layout with the implementation owner; no new revision number is allocated here.

1. Quiesce all writers/workers/webhooks; obtain a migration lock and bounded
   table locks. Verify one exact supported source revision and the entire source
   signature (columns, defaults, constraints, triggers, FKs), not just table
   existence. Reject unknown/mixed/partially migrated schemas. Capture synthetic
   rehearsal baselines and require a tested backup/restore plan for later rollout.
2. For remote0009 rename its outbox to `provider_invitation_deliveries`, preserving
   IDs, rows, ciphertext and event references. PostgreSQL preserves FK object
   references on rename, but inspect the resulting FK explicitly. Preserve or
   deliberately rename existing constraint/index names without recreating rows.
   Remote0008 has no outbox; create the target provider structures instead.
3. Materialize the missing integration assignment migration using its exact
   frozen v1 semantics and install its trigger. Create the empty local queue with
   all original constraints. Keep remote `is_active`, add version=1 and its check.
   Add the final notice schema with existing decisions unknown; do not infer old
   notice copy, consent proof, retention days, or deadlines. Apply C-equivalent
   schema work without attempting either colliding ancestor chain.
4. Verify target schema equivalence and row invariants in the same transaction;
   only then translate the Alembic version to C, recording source revision and
   schema fingerprint in a durable migration receipt. On any failure roll back
   DDL/data/version together. Never expose a generic unvalidated `stamp head`
   shortcut. A second run must identify the completed target and perform no writes.
5. Start only the reconciled application after validation. Retain legacy scripts
   for provenance/rehearsal, not automatic downgrade across the bridge.

If the reconciler instead chooses compatibility-aware edits to historical upgrade
bodies, retain all IDs/parents and explicitly document that changed behavior.
`has_table`/`has_column` skips alone are insufficient: validate full shape and add
missing constraints, preserve existing false/version values, and ensure a new
descendant fixes already-applied remote0009 (its edited body will never rerun).
Prove fresh traversal in both branch orders plus every populated starting head.
Without that evidence, a merge-head success on an empty database is not acceptance.

## Stronger behavior and rollback gates

- Preserve organization/actor/target row locking, actor revalidation, last-active-
  admin protection, strict expected-version conflicts, version increments and
  no-op semantics from integration account service. Remote model replacement
  drops `version` and its check; wholesale replacement is a regression.
- A duplicate provider subject in a second tenant must fail the global unique
  constraint. Preserve stable subjects exactly, including provider prefixes;
  Auth0 adoption does not authorize changing historical identities to emails.
- Preserve assignment trigger even for NULL-to-value updates: integration0008
  freezes unknown NULL history too. Allow ordinary revocation/privacy changes
  without mutating assignments. Do not recompute old reports with new algorithms.
- Retain local fail-closed uncertain-send handling, credential wiping, expiry,
  bounded claims, idempotency conflict and privacy cancellation. Preserve provider
  webhook deduplication, delivery metadata and request tombstones independently.
- Remote0008 downgrade currently drops deactivation state without a guard;
  remote0009 downgrade explicitly discards queued messages and event history.
  Do not expose those paths as safe rollback. Local0009 guards only queued/sending
  and can still discard terminal tombstones; that is insufficient for a bridge.
- Block schema downgrade across convergence while either store contains rows,
  webhook dedupe exists, any user is disabled, or assignment/notice/consent evidence
  would be lost. Prefer retaining the schema and rolling back only compatible
  application code. Integration0010 locks users before checking disabled accounts;
  maintain equivalent concurrency protection for every guard. Never reset versions
  to enable downgrade or let an older application bypass deactivation.
- Keep notice0011 owner's rollback/evidence guards; pending contract is not proof
  of implementation. Preserve all-or-none snapshot fields, immutable-once rules,
  unknown historical decisions and the separate immutable assignment invariant.

## Required populated fixtures and assertions

Use synthetic, isolated PostgreSQL databases owned by the implementation/test lane;
PG5612 was reserved for this reviewer only if needed and was not started. SQLite
may supplement, but cannot establish PostgreSQL locks or trigger correctness.

| Start | Exact populated fixture | Required result |
| --- | --- | --- |
| Common0007 | Two organizations; active users; unused invite; canonical-v1 submitted invite/report; malformed/unknown definition; anonymized assessment; consented and declined invites | Only eligible v1 assignments backfilled; unknown/anonymized stay NULL; existing report/consent/deadline/audit data unchanged |
| Remote0008 | Active and disabled users in both tenants; shared email across tenants with distinct subjects | Disabled remains disabled; versions become 1; global subject uniqueness and tenant email uniqueness remain |
| Remote0009 | One row per all nine statuses; valid synthetic encrypted queued/retrying messages; exhausted retry; duplicate webhook retry; replaced invite; shared request UUID across tenants; provider message IDs | Preserve all IDs, ciphertext bytes/text, attempt counts, retry clocks, event rows and dedupe; no local rows fabricated and no sends during migration |
| Integration0008 | Both populated and intentionally NULL immutable assignments | Neither overwritten nor guessed; assignment mutation rejected after upgrade |
| Integration0009 | One row per all six states; queued/sending credentials; uncertain with no credentials; attempt_started_at; expiry boundary; idempotency tombstones | Exact local data/check preservation; uncertain never retried; provider table empty |
| Integration0010 | Disabled account; version 7 account; two admins; stale expected_version=6 | Version remains 7; stale write conflicts; last-admin and actor-deactivation races retain behavior |
| Notice0011 | Existing legacy decisions with NULL evidence; issued/first_presented/legacy_decision snapshots; digest-recorded and legacy-unverified decisions | Exact snapshot/hash/origin/evidence retained; no fabricated legacy backfill; stale digest produces zero decision writes |
| Failure/retry | Unexpected column/type, missing check, conflicting table shapes, migration exception after rename and before version update | Fail closed; transaction restores original table/version/data; successful rerun is a no-op |
| Downgrade/races | Pending sends, terminal request tombstones, webhook events, disabled users, notice evidence; simultaneous writer during guard | Downgrade rejected atomically; no lost credential/evidence, reenabled account, or duplicated send |

Compare before/after ordered primary keys and canonical row digests for unchanged
tables, and explicit values for timestamps/JSON/ciphertext/identity/version fields.
Assert every check/unique/FK by attempted violating writes in rolled-back test
transactions, including cross-tenant subject collision and duplicate provider event.
Inspect trigger definitions and both indexes; test ORM metadata creation separately
from migrations so model/migration drift cannot hide behind `create_all`.

## Review receipt

Read both histories, model diff, common0002 subject constraint, integration account
locking/version code, migration tests, and notice owner contract. No source edits
or runtime verification are claimed. Final documentation validation is
`git diff --check`; populated bridge implementation/rehearsal and final combined
checks remain with the reconciliation/coordinator lanes.
