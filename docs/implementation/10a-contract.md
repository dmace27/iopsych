# 10A additive privacy lifecycle contract

Prepared 2026-11-04 against `c20b3eddc21f73870a87fb27503151da43be8048` in
`AbhiNutakki/iopsych-privacy-contract`. **Proposal and inventory only: no code,
schema, policy approval, or package 10A acceptance is delivered.**

Authority: [final plan](../../final-implementation-plan.md), packages 6C, 8A,
9A–B and 10A–C; [specification](../../mvp-spec.md), sections 3, 9–12, 16–17;
[finish](../../finish.md), tasks 9–10; [progress](progress.md);
[pending decisions](6b-decisions.md), D06–D10. Read applicable
`apps/web/AGENTS.md`; no web code changed. This dispatch owns only this
document. No runtime, database, provider, or reserved port was used.

## Current persisted inventory

These are actual implementation names, not the specification's conceptual
`candidate_assessments`/response tables. `id` and `created_at` below come from
model mixins. Source: [models](../../apps/api/app/database/models.py).

| Record               | Exact retained fields                                                                                                                                      | Relationship / lifecycle                                                                                                                                                                                            |
| -------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `assessment_invites` | `id`, `created_at`, `role_profile_id`, `email`, `token_hash`, `expires_at`, `status`, `sent_at`, `revoked_at`, `revoked_by`                                | Tenant through profile → role → organization; unique token hash; email is the stored candidate identity, no display name. Status is `pending_delivery`, `active`, `consented`, `declined`, `revoked`, or `expired`. |
| `candidate_consents` | `id`, `created_at`, `invite_id`, `decision`, `notice_version`                                                                                              | One per invite; decision `consent` or `decline`; opposite decision conflicts. No withdrawal or notice-content snapshot.                                                                                             |
| `assessments`        | `id`, `created_at`, `invite_id`, `consent_id`, `submitted_at`, `retention_expires_at`, `anonymized_at`, `definition_json`, `responses_json`, `scores_json` | One per invite. Created on submission, not consent; nullable submission timestamp is not an implemented draft API. JSON stores full definition, canonical block responses and server scores.                        |
| `alignment_reports`  | `id`, `created_at`, `assessment_id`, `role_profile_id`, `algorithm_version`, `result_json`                                                                 | Unique assessment/profile/algorithm; immutable saved interpretation by service convention.                                                                                                                          |
| `alignment_items`    | `report_id`, `construct_key`, `classification`, `confidence`, `explanation_json`, `questions_json`                                                         | Derived report child rows; no independent retention deadline.                                                                                                                                                       |
| `audit_events`       | `id`, `created_at`, `organization_id`, `actor_id`, `event_type`, `entity_type`, `entity_id`, `metadata_json`                                               | Append-only ORM and DB guards; UUID relationships and timestamps remain linkable. No retention/purge mechanism.                                                                                                     |

Role/profile/ratings and internal users are context, not candidate-owned
records: privacy deletion does not delete the role or its approval history.
Foreign keys mostly use `RESTRICT`; deletion order is therefore explicit, not an
assumed cascade.

[Invitation service](../../apps/api/app/invitations/service.py) creates a
pending invite, flushes, sends, then marks active and commits/flushes. Delivery
failure rolls back; send-before-final-commit can leave an emailed link without a
committed invite. Revoke changes status/time/actor; it does not erase data.
Expiry is enforced on access and can update status then; there is no unopened
invite cleanup. Consent creates its record and changes invite status. Submission
locks the invite, validates consent, loads the current definition file, stores
scores and `submitted_at + PRIVACY_RETENTION_DAYS`; equal retries return the
same assessment ID and changed answers conflict.

[Notice response](../../apps/api/app/invitations/schemas.py) has `version`,
`purpose`, `data_use`, `retention`, `accommodation_contact_email`,
`privacy_contact_email`, `decline_without_penalty`. It is rebuilt from live
settings even after consent. Stored notice version alone cannot prove the text
seen. Current retention default is **90 days**, batch **100**, configurable in
[privacy settings](../../apps/api/app/privacy/config.py); these are
implementation defaults, not approved policy. Migration 0007 left legacy
deadlines NULL; the service derives those using current settings on each run.

[Report generation](../../apps/api/app/reports/service.py) locks the assessment,
checks affirmative consent, submission, approved historical profile and absence
of `anonymized_at`. Revoking an invite alone does **not** disable report
generation or reading. Do not use revocation as a synonym for withdrawal.

## Current rights, side stores, and limitations

[Privacy routes](../../apps/api/app/privacy/router.py) are admin-only:
`POST /v1/candidates/{assessment_id}/export`,
`DELETE /v1/candidates/{assessment_id}`, `GET /v1/privacy/status`,
`GET /v1/privacy/audit-events`, `POST /v1/privacy/retention/run`.
[Service](../../apps/api/app/privacy/service.py) scopes through the tenant
chain. There is no candidate self-service rights API or invitation-based rights
lookup.

Export schema `1.0` contains generation time; organization name, role title and
profile version; invitation ID/email/status/created/sent/expiry/revoked times;
consent ID/decision/notice version/time; assessment
ID/created/submitted/deadline and all three JSON snapshots; reports with
ID/time/algorithm/result; related activity type/entity/ID/time/details. It
excludes token hash, raw token and internal actor ID. Report child rows are not
independently serialized; their report result snapshot is exported. It cannot
export a record without an assessment. Export uses multiple reads without a
shared deletion lock. Downloads are immediate `no-store` JSON attachments; no
server export artifact table exists.

Anonymization locks the assessment, removes report items then reports, replaces
all assessment JSON with `{"anonymized": true}`, replaces email with
`deleted-<invite UUID hex>@privacy.invalid`, replaces token hash with SHA-256 of
`anonymized:<invite UUID>`, and revokes the invite. It retains IDs, links,
timestamps, consent decision/version, actor references and audit records.
Repeated calls are idempotent. Call this an **application tombstone**, not proof
of irreversible anonymity. Retention selects only due submitted assessments,
locks with `SKIP LOCKED`, and runs one bounded batch; the CLI has no scheduler,
backlog drain or backup replay. Status counts assessments only.

| Side store                         | Exact current content / behavior                                                                                                                     | Privacy boundary                                                                                                                                                                                                  |
| ---------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Email boundary                     | `InvitationEmail(recipient_email, subject, text_body, html_body)`; body includes organization, bearer URL, expiry and privacy contact                | No answers/scores accepted by builder. Default adapter fails closed; no durable delivery/outbox/provider-message row in this baseline. Future local capture and external processors need separate purge evidence. |
| Browser draft                      | `iopsych.candidate.v1.<invitation_id>.draft`: `{saved_at, response_set}`                                                                             | `response_set` is the shared assessment response set, containing definition ID/version and complete answered/skipped block choices. No server draft/context store.                                                |
| Browser receipt                    | Same prefix plus `.completion`: `{assessment_id, submitted_at}`                                                                                      | Answer-free receipt; timestamp is client acknowledgement time. Old answer-bearing completion envelopes are rejected/removed on access.                                                                            |
| Browser cleanup                    | 24-hour max age from saved/receipt timestamp, also bounded by supplied invite expiry; clear-device and successful submission remove keys best-effort | Cleanup is on access, not background erasure; storage denial is handled. Offline devices and failed removal cannot be remotely wiped.                                                                             |
| Audit / logs                       | Consent decision, scoring/algorithm version, deletion reason/report count; middleware records HTTP method/status/outcome and target UUID             | Metadata is currently small, but arbitrary future metadata must not include email, tokens, answers, notes or exports. Existing UUID linkage survives deletion.                                                    |
| Backups / downloaded files / notes | No implemented backup deletion replay or managed export store; external notes destination unselected                                                 | Local downloaded copies and mailbox copies are outside DB deletion. Do not claim they were erased.                                                                                                                |

Storage evidence: [helper](../../apps/web/lib/candidate-storage.ts),
[envelopes](../../apps/web/lib/candidate-contracts.ts),
[9A report](9a-report.md). No optional candidate context or server `/responses`
route currently exists; D06/D07 recommendations are still pending, not
permission to omit those journeys.

## 6C compatibility boundary

Read-only sibling source:
`../iopsych-6c-versions/docs/implementation/6c-contract.md`, SHA-256
`c03bb8e4859b63ba6edc95842ea251e753c7e8456bbd81fe9b0f88cd739c00ed`. Its worktree
HEAD was `4638236` with uncommitted implementation, so the contract is a handoff
dependency, not integrated/runtime evidence for this branch.

6C adds nullable immutable `assessment_invites.assignment_json`:
`{contract_version: 1, definition: <full definition>, definition_sha256, matching_algorithm_version}`.
Hashing uses sorted compact UTF-8 JSON with unescaped Unicode. The consent-gated
definition endpoint returns definition plus assignment definition ID/version,
scoring version, matching version and hash. Existing landing/consent/submit
shapes remain unchanged. New assignments require reviewed content unless
explicitly synthetic; no reviewed entry exists. Retired pinned history remains
readable. Unknown/malformed assignments fail closed.

Its reserved migration `20261104_0008` uses frozen v1 assets: unsubmitted legacy
invites get v1; recognized submitted history gets its original definition;
unknown/malformed or anonymized submitted history remains NULL. It never
reconstructs deleted responses. Mutation guards forbid even NULL-to-value
assignment edits after migration. Privacy must leave this candidate-answer-free
snapshot untouched; do not insert policy, email, notes or responses into it.
Assignment immutability does not approve unlimited retention of its invite link.

## Proposed additive contract, subject to engineering agreement

Use the existing invite as the privacy subject anchor; do not create a second
candidate identity or merge people by equal email. An admin can explicitly
select multiple verified invite IDs within one tenant for a request. Keep
existing assessment routes and schema `1.0` responses compatible.

1. Add a separate one-to-one privacy lifecycle record keyed by `invite_id` (new
   model/migration to be assigned later). Proposed fields:
   `policy_snapshot_json`, `policy_sha256`, `snapshot_provenance`,
   `snapshotted_at`, `accepted_policy_sha256`, `retention_expires_at`,
   `use_suspended_at`, `erased_at`, `erasure_reason`. Policy snapshot shape v1:
   `schema_version`, `policy_version`, the complete existing `ConsentNotice`
   object, and retention rules `{category: {anchor, duration_seconds}}`. Only
   approved finite durations belong in a real-pilot snapshot. Provenance is
   `issued_snapshot`, `legacy_verified`, or `legacy_unknown`; unknown content is
   NULL, never reconstructed from today's settings. Mutable lifecycle timestamps
   must be separate from immutable snapshot fields.
2. Freeze policy at issuance alongside, but outside, 6C assignment. Consent
   records the exact hash served under the invite lock; the landing returns the
   existing notice shape from that snapshot, and submission computes its
   deadline from that policy. Never silently extend a stored deadline on config
   changes. Reissuing under changed terms creates a new invite; legacy
   reconciliation is separately recorded. A stale consent form must not accept
   different text: versioned consent request with expected policy hash is
   required if a policy can change between rendering and consent. The current
   strict client schemas require coordinated rollout before any new
   response/request fields.
3. Propose new admin routes under `/v1/privacy/invitations/{invite_id}`:
   `POST /export`, `DELETE /data`. Export envelope `schema_version: "2.0"`
   contains the existing invitation/context, nullable consent/assessment,
   reports, related activity, plus privacy snapshot/provenance/deadline and
   assignment metadata. Include actual stored draft/context only if 9B
   introduces them; absence is not an empty submitted answer. Never export
   delivery credentials. Deletion returns invite ID, nullable assessment ID,
   erased timestamp, already-erased flag and counts. Cross-tenant/missing IDs
   share existing 404 behavior; erased exports return 410. Use no-store and
   atomic required audits.
4. Erasure covers the whole invite subtree: invalidate credential and contact,
   wipe response/score/context/draft payloads, delete every derived report/item,
   cancel queued delivery and purge queued credentials. Preserve only explicitly
   approved tombstone/consent/audit evidence. Repeat requests must not
   reactivate data. Add related-event traversal before deleting report IDs, so
   later rights audit remains discoverable without recording content.
5. Withdrawal is a separate verified action, never rewriting initial consent to
   decline. Proposed handling is immediate use suspension, then deletion
   according to approved policy; report/list/read/generate and draft/submit
   gates all consult suspension/erasure. A suspended state is not implemented by
   current revoke. Corrections preserve original submissions/reports: use a
   separately attributed correction or new linked invite, with
   visibility/deletion rules approved first. Do not expose these actions until
   their policy and verification are agreed.

## Deletion and retention matrix

Symbols below denote **unapproved policy parameters**, not new defaults. D10's
7-day/24-hour/30-day/90-day suggestions remain suggestions. Current 90-day
server and 24-hour device settings are not endorsements of those proposals.
Cleanup latency must be an explicit operational SLA; it must not extend a
promised maximum retention period without notice and approval.

| Category / anchor                              | Current coverage                                       | Proposed deadline and erasure / retained minimum                                                                                                                                                        |
| ---------------------------------------------- | ------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Pending delivery / issuance                    | Email/hash can persist; no assessment means no cleanup | `created_at + T_pending`; cancel sending, erase recipient/credential and queued copies; retain approved event/tombstone only.                                                                           |
| Active unopened/opened / invite expiry         | Access enforces expiry; no identity cleanup            | `expires_at + T_unsubmitted_grace`; erase contact/hash; no synthetic consent record. Opening must not reset the clock.                                                                                  |
| Declined / consent decision time               | Decision retained indefinitely without assessment      | `consent.created_at + T_decline`; disable access immediately, erase contact and any stray drafts; minimal decision/policy evidence only for approved evidence period.                                   |
| Revoked / revocation time                      | Credential disabled; payloads retained                 | `revoked_at + T_revoke` for unsubmitted; submitted data follows approved withdrawal/deletion policy, not an assumed restart of retention.                                                               |
| Consented, unsubmitted / invite expiry         | No assessment rights path or deadline                  | `expires_at + T_unsubmitted_grace`; erase invite identity and any future server drafts/context; retain only approved evidence.                                                                          |
| Server draft/context if implemented            | Absent                                                 | Must not outlive parent deadline; submission atomically removes draft. Export latest retained draft revision and context; clear on deletion/withdrawal.                                                 |
| Submitted / submission time                    | Stored deadline; legacy live-setting fallback          | `submitted_at + T_submitted` frozen from assigned policy; erase identity, all three assessment JSON payloads, context, reports/items. Existing earlier explicit deadlines are not extended by backfill. |
| Derived reports/items                          | Removed with assessment anonymization                  | Same or earlier deadline as assessment, never reset by report generation/read. Block all use after suspension/erasure.                                                                                  |
| Device draft/receipt / save or acknowledgement | 24-hour TTL plus invite expiry on access               | Bound by parent expiry and approved device TTL; clear on submit and clear-device, purge legacy payloads. Explain offline and removal-failure limits.                                                    |
| Delivery capture/outbox/provider copies        | Adapter only; provider unconfigured                    | Credential deadline no later than link expiry; purge on cancellation/deletion and terminal send per selected delivery design. Capture/mailbox retention needs owner and explicit finite policy.         |
| Export / request                               | In-memory response/download only                       | No new persistent export artifact necessary. If introduced, independently authorized download TTL and deletion hook; no automatic email attachment. Already downloaded copies cannot be recalled.       |
| Erased tombstone / erasure time                | Linkable IDs/times/consent/audits persist              | Minimal replay identifiers, scope/reason/time; finite evidence/replay period approved by privacy/operations. Never label all remaining data anonymous.                                                  |
| Audit / event time                             | Append-only, no purge                                  | Approved finite audit period or documented exception. Do not bypass immutable triggers or promise to strip old links in-place; any expiry/partition strategy needs separate controlled design.          |
| Backups / backup time                          | No replay implemented                                  | Approved backup lifetime; restricted deletion ledger survives restore and replays before access. Ledger must outlive every affected backup and any required replay window.                              |
| External notes / destination policy            | No selected destination                                | Rights request remains open for external propagation until owner confirms; no DB endpoint can attest external erasure.                                                                                  |

## Transactions, backfill and required tests

The existing report/erasure assessment lock is useful but insufficient for
invite-only cleanup and export consistency. Standardize lock order **invite →
assessment → report children**, then profile if required; update existing report
paths together, since they currently lock assessment then profile. Do not add an
invite-first privacy lock while leaving reverse-order writers unchecked.

Use PostgreSQL barriers and two independent connections, not sleeps or SQLite
claims, to prove:

- Consent/submit versus invite erasure: either submission commits first and is
  included in erasure, or erasure commits first and submission is rejected. No
  response/score rows appear after successful erasure.
- Generate/read/list/export versus erasure: operations linearize under the same
  subject lock. An export admitted before erasure may finish delivering
  afterward; never promise recall of bytes already released. Requests admitted
  after erasure expose no candidate payload. Multi-query exports must not mix
  pre/post-erasure data. Hold locks through export materialization and required
  audit commit.
- Withdrawal versus report generation/read, draft save versus submit/delete,
  duplicate deletes and two retention workers: no reactivation, duplicate
  effects, deadlock or surviving report items. `SKIP LOCKED` workers later drain
  skipped rows without starvation; large backlogs are processed in bounded
  transactions.
- Commit/audit failure rolls back all local erasure changes. Delivery send
  versus erasure cannot be made atomic by a DB lock alone: cancellation checks,
  bounded claim/lease and purge after uncertain acceptance must be tested in 8A;
  late callbacks never restore recipient data or reactivate links.

Backfill must follow 6C migration 0008 with a coordinator-assigned slot; none is
reserved here. Inventory every lifecycle category first. Persist observed
existing submission deadlines unchanged. Legacy NULL deadline policy requires
approval; report its count instead of silently assigning a new retention period.
Recover historic notice text only from verified immutable release/config
evidence; a version string is insufficient. Label missing evidence
`legacy_unknown`; any requirement to re-consent/reissue is an explicit decision.
Never restore deleted JSON or modify 6C snapshots, even for migration
convenience.

Populated upgrade fixtures must include pending/active/expired/declined/revoked,
consented-unsubmitted, submitted with explicit and NULL deadline, anonymized,
unknown assignment, old notice version, reports/items and immutable audit
events. Check SQLite and PostgreSQL constraints, strict old clients,
tenant-negative paths, unknown policies, restart/retry idempotency, timezone
boundaries and changed live configuration. Compare pre/post snapshots and assert
no resurrection. Retention must cover every matrix row implemented in the
database; backup replay and browser cleanup require their own integration
evidence.

Existing targeted tests inspected, **not executed in this documentation task**:
`tests/test_privacy.py` covers admin export/anonymization, retention/audit
bounds, submission deadlines and scheduler entrypoint;
`tests/test_reports_postgres.py` covers duplicate submissions/reports and
skip-locked retention. These do not establish the proposed lifecycle/race
guarantees. No broad suite or DB was run.

## Smallest remaining owner decisions

1. **Privacy/product:** approve actual notice and finite per-category clocks,
   anchors, evidence/audit/backup exceptions and cleanup SLA. Resolve D10
   against current 90-day behavior; do not treat its suggested numbers as
   accepted.
2. **Privacy/support:** select withdrawal effect, correction method and verified
   rights handling after link expiry. A maintained support channel plus
   documented verification is the smallest first workflow; email knowledge alone
   is not proof. If a fresh challenge is used, bound attempts/expiry, store only
   a hash, and do not persist identity documents without a justified
   requirement.
3. **Product/privacy:** resolve D06/D07 device-only versus server resume and
   optional context, with explicit specification updates for any reduction.
4. **Operations/privacy:** name contacts and owners for delivery copies,
   external notes (if selected), backup lifetime and replay. Provider/hosting
   selection is separate; no new infrastructure is justified by this document
   alone.

## Safe next dispatch and exact ownership

Smallest useful decision-independent implementation: **serialize current
assessment export with existing assessment anonymization and test it**, without
adding routes, fields, policies, migrations or lifecycle promises. Scope is the
existing submitted-data path only, not full 10A.

Exclusive files to allocate:

- `apps/api/app/privacy/service.py`: acquire the existing assessment lock during
  export and materialize its complete envelope before the audited request
  commits; preserve export schema and tenant/error behavior.
- `apps/api/tests/test_privacy_export_postgres.py` (new): isolated-schema,
  synthetic-only two-connection export/delete interleavings, both lock orders,
  no mixed snapshot, post-erasure rejection and foreign-tenant negatives.
- `docs/implementation/10a-export-lock-report.md` (new): commands/results and
  bounded guarantee, including delivery of a pre-erasure export after deletion.

No report/invite/schema/shared-contract edits are needed for that slice because
current deletion already locks `Assessment`. Coordinate allocation before edits;
6C currently owns `test_privacy.py`, so leave it untouched. Do not change export
notice/schema to v2 during this slice. Use an explicitly allocated disposable
local PostgreSQL schema/database; do not inherit an ambient production URL or
reset existing DBs. Ports 3121/8121/5561 remain reserved and unused here. Run
only the focused new PostgreSQL test and relevant existing privacy test file; a
skipped PostgreSQL run is not success for the concurrency acceptance criterion.

For full lifecycle work, coordinate subsequent exclusive ownership of invite and
report services, privacy models/routes/schema, client strict schemas and a new
migration after 6C lands. This document grants none of those edits
automatically.

## Dispatch verification

Only this document is changed. Validation: local Prettier for this file and
`git diff --check`; results recorded in the worker completion message. No code
execution, runtime startup, real email, provider call, deployment, purchase,
production secret access, database reset, or scientific/retention approval was
performed. Commit ID is supplied in the orchestration handoff rather than a
self-referential document revision.
