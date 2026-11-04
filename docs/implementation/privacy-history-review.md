# Related privacy history review

Reviewed `a48f755029c146b26710a1ae835bef74d7c7d9f4` and
`2ec0b5793914e90acd69cbc1f68320e4fe73e00e` at worktree baseline `3111919`.
Read the final implementation plan, applicable web AGENTS guidance, existing
10A contract and privacy refresh receipt. Fast mode was observed, not toggled,
in this worker's terminal metadata (`GPT-6-Astra medium fast`). Initial application
review was read-only apart from a temporary, removed reproduction test. The
coordinator then authorized a narrow component fix and dedicated callback tests;
those are committed separately from this report. No critical isolation defect
was found. The installed Next.js use-client guide was read for the component work.

## Finding PH-01: obsolete pagination callbacks publish status (P2, fixed)

In `apps/web/app/privacy/privacy-workspace.tsx:246`, the row update checks
`current.auditEvents === state.auditEvents`, but the subsequent announcement,
catch error and finally loading reset have no equivalent scope/request guard.
Start loading an older page for A, enter B and load its history, then reject
A's deferred request. B's successfully loaded history now shows A's error.
A successful obsolete response can similarly announce additional events that
were deliberately not appended. Loading another history scope is permitted
while pagination is pending.

A temporary jsdom reproduction followed precisely that sequence and asserted
the obsolete error under B's scope: **1 passed, 2 unrelated tests skipped**.
The initial reproduction was removed to preserve file ownership. This is misleading
feedback, not demonstrated cross-tenant disclosure or row corruption. Gate
all callback effects on the active request/scope, including errors and live
announcements. A pending page can also finish after deletion/retention refresh;
the same unguarded status effects can replace a newer operation announcement
or refresh error. The retention interleaving is covered by the subsequent fix
tests; deletion was inspected separately. The authoritative deletion receipt and confirmation map are separate
state and are not overwritten by this callback.

The authorized fix adds a request generation checked before publishing rows,
announcements, errors or loading resets. History reload, discovery, export,
deletion and retention invalidate pending pagination callbacks; pagination is
disabled while discovery or mutation is active. Starting a new
page advances the generation, so an old completion cannot unlock the newer
request. Four dedicated tests cover both obsolete success/failure after scope
replacement with a newer page pending, and after retention succeeds but its
refresh fails. These pass and preserve the newer feedback and row count.

## Tenant lineage, cursor and actual writers

`PrivacyService.list_audit_events` proves ownership through assessment → invite
→ profile → role organization before filtering organization-owned audit rows.
Each related UUID is paired with its entity type, including reports selected
by assessment ID. UUID collisions with unrelated entity types and sibling or
foreign events are excluded. `assessment_id` and `entity_id` together reject
with 422. The related cursor reuses the full statement, including exact
`event_type`, before applying descending `(created_at, id)` pagination. A
cursor from another related set or event filter rejects with 404. Legacy
entity/default cursor behavior remains intentionally less strict and unchanged.

Actual writers agree with the query, with an important test-fixture distinction:

- Invitation create/revoke decorators use `assessment_invite`; create assigns
  the produced invite ID with `set_audit_entity`. Queue/delivery writers use the
  same entity type and invite ID.
- `CandidateInvitationService.record_consent` calls `_append_audit` for
  `candidate_consent.recorded`; that helper writes **`assessment_invite` and
  the invite ID**, not `candidate_consent` and consent ID. Consent therefore
  appears through the invite branch. The separate consent branch is harmless
  but is not evidence that a production consent-entity writer exists.
- Submission writes `assessment` with assessment ID. Report generation/read/
  trace decorators and generation service events use `alignment_report` with
  report ID; successful generation assigns the produced report ID explicitly.
  Failed creation before an entity exists can fall back to actor ID and is not
  promised as linked history. Role-wide submission/list events remain excluded.

The API fixture invents `fixture.related` for all four entity types; UI fixtures
use `invitation`, `consent`, `report`. Those tests prove filtering/rendering,
not production writer integration. Add a focused real consent/invite/report
writer journey when fixing PH-01 or extending coverage; no missing successful
consent event is established by the naming difference alone.

## Errors, selection and authoritative receipts

API SecurityHeadersMiddleware applies `Cache-Control: no-store` to success and
handled errors; the outer unexpected-error handler adds the same headers.
The internal proxy and API client also use no-store. The audit route's new
success header is consistent with those existing boundaries. Admin checks,
tenant-not-found responses and validation errors remain enforced; audit append
failure remains fail-closed. These are source findings plus the focused API
authorization tests, not a new exhaustive error-injection run.

Displayed scope and pagination are taken from loaded `auditAssessmentId`, not
the editable selection. Ordinary reload replaces the workspace with loading
state, preventing another visible selection action during that load. Mutation
and lookup controls lock selection while their work is pending. On successful
deletion, the returned assessment ID/time is retained in the confirmation map
and deletion receipt before refresh; retention retains every returned ID and
does not fabricate a timestamp. Refresh failure reports completed operation
plus failed refresh. A stale discovery row cannot undo the authoritative map.
The 18 existing workspace tests still pass. No receipt-preservation regression
was found in the reviewed changes; PH-01 was limited to callback effects.

## Deletion, restore and notice boundary

Deletion removes report items and reports, but retains assessment/invite/consent
links and audit events. Consequently the related report-ID subquery loses
deleted-report linkage even though its audit rows remain organization-readable.
The existing targeted test explicitly demonstrates this limitation. A cursor
pointing to a now-unlinked report event can subsequently return 404. This is
current-record traversal, not complete historical lineage or a deletion ledger.
The authorized UI fix adds a qualification that only currently linked records
appear and deleted-report events remain in organization-wide history.

Current anonymization erases assessment JSON, substitutes email/token hash,
revokes access and cancels delivery, while preserving linkable IDs, dates,
consent and audit evidence. It does not establish irreversible anonymity or
erase downloaded exports, provider copies or backups. At this baseline,
`scripts/verification/local_restore_rehearsal.py:461` explicitly records the
unsafe pre-deletion restore counterexample and says external replay is not
implemented/proven. No restore/container run was performed here; later isolated
journal work must supply its own revision-linked evidence. No new retention
duration, policy approval or production replay guarantee is inferred.

Notice snapshots remain a separate **contract-only** follow-up governed by
`10a-contract.md`: existing consent stores a version while presentation uses
live settings. Exact historical text must not be reconstructed as fact from
today's settings. Preserve immutable assignments and existing receipts; agree
snapshot shape/provenance, legacy unknown handling, strict-client compatibility
and migration ownership before implementation. This review changes no notice
contract, schema, migration or retention rule.

## Verification and compact receipt

- API: `.venv/bin/python -m pytest apps/api/tests/test_privacy_related_audit.py -q`
  executed four passing tests against in-memory SQLite; command exit **1** from
  the repository-wide 100% coverage threshold (58.28% for this selected slice).
  This is not a passing global coverage gate; no full-suite retry was run.
- Web: from `apps/web`, `../../node_modules/.bin/vitest run
  app/privacy/privacy-audit.test.tsx app/privacy/privacy-workspace.test.tsx
  lib/privacy-audit-client.test.ts`: **22 passed**, exit 0.
- Temporary PH-01 reproduction: same runner, only privacy-audit test file with
  `-t 'review reproduction'`: **1 passed, 2 skipped**, exit 0; removed afterward.
- After the authorized fix, the same three web files plus dedicated
  `app/privacy/privacy-audit-callbacks.test.tsx`: **26 passed**, exit 0. Focused
  ESLint on the component and new tests passed; Prettier formatted both files.
- No browser run or browser dependency installation was needed. Existing local
  dependencies sufficed; any future browser install must remain separate via
  `npm ci --prefix tests/browser`. No server, protected port, existing database,
  container, real mail, push, deployment or purchase was used.

Delivery: fix `5f21c5b` and a separate documentation commit on
`AbhiNutakki/iopsych-privacy-history-review`; exact IDs are sent in the worker
completion receipt. Remaining work is real-writer integration coverage and
separately owned notice/restore contracts. This review does not duplicate or
close package acceptance.
