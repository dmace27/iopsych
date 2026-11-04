# Notice integration review

Read-only application review on November 4, 2026. This document is the only
owned change. No application edits, database operations, ports, mail, deployment,
or policy changes were performed. Local configuration reports `service_tier =
"fast"`; it was inspected without changing it.

## Revision scope

- Pure module: `219f1ef3852cd06bfc27ac8f7d2967f20fc10693`.
- Review checkout baseline: `f2e6329`.
- Candidate UI: `645b4c5d9f3b5d2b39f3f4560bf7f6cfa9dc1bc2`.
- Wire/client integration: `f42fef868452b9c281cbc1a92ace8360439f60a3`.
- API integration: final checkpoint
  `1aec1596d9c95625486903ddeaa6b45490f546e8`, reviewed after owner commit.
  Initial observations below explicitly describe earlier uncommitted drafts.

Read `final-implementation-plan.md`, the applicable web `AGENTS.md`, and
`docs/implementation/notice-snapshot-contract.md`. This review does not declare
phase 10A complete or approve notice content.

## Findings communicated before integration

1. **High: privacy export client rejects the new response.** The uncommitted API
   adds six fields to `ExportConsent`, including when their values are null.
   `apps/web/lib/privacy-contracts.ts` uses a strict consent object that accepts
   none of these fields. Candidate UI revision `645b4c5` does not change this
   schema. Admin export therefore fails client parsing. Update the export
   contract and its regression together before enabling API additions.
2. **Medium: incomplete database invariants in the initial API draft.** Migration
   0011 prevents replacement of a populated snapshot, but initially omitted
   complete-or-null, digest shape, provenance, and post-decision initialization
   guards. Model-created databases initially lacked notice guards entirely.
   Without the post-decision guard, historical consent can acquire a newly
   supplied snapshot and be relabeled `legacy_unverified` instead of unknown.
   Service paths already avoid that operation, so this is a persistence-boundary
   issue rather than a demonstrated public API exploit.
3. **Rollout requirement: old strict candidate clients reject additive fields.**
   New optional fields support old-server/new-client operation, but cannot make
   old-client/new-server operation compatible. Deploy the updated client before
   API exposure, with an explicit strategy for already-open old tabs, or use
   capability negotiation. Do not describe unconditional same-v1 additions as
   universally backward compatible.
4. **Retained-content limitation:** anonymization leaves the immutable notice,
   including configurable contacts and free-form copy. Existing settings permit
   identifiable contact addresses and arbitrary text. These fields must not
   carry candidate-specific information; documentation must describe retention
   honestly. Rewriting historical notices during deletion would break the exact
   hash contract and is not proposed here. Content/privacy approval remains an
   external gate.
5. **Follow-up on evolving capability negotiation:** the later API draft gates
   candidate metadata on `X-IOPsych-Notice-Snapshot: 1`. UI `645b4c5` does not
   send that header, and the candidate proxy rebuilds upstream headers without
   forwarding it. Update both caller and proxy with a regression; forward only
   explicit client opt-in rather than setting the header for old tabs. Otherwise
   the new UI silently makes digest-less decisions despite supporting digests.

## Contract and security observations

- The pure helper requires exact keys and types, valid UTF-8, bounded version
  length and retention days, and lowercase SHA-256. It preserves text code
  points and hashes every notice field plus retention days. Returned objects
  are detached. No defect found in the reviewed pure implementation; its
  previously reported 46 tests were not repeated.
- Initial API draft freezes the same settings-rendered copy and retention days
  for both direct and queued issuance. Existing queued idempotency replay returns
  the original invitation before issuing a new snapshot; request digest remains
  based on the original request, so config changes do not silently replace it.
- GET and POST lock the invitation with PostgreSQL `FOR UPDATE OF` and refresh
  ORM state. Concurrent decisions re-read consent after this lock. Supplied stale
  digest is rejected before consent/status/audit writes. SQLite is not evidence
  of equivalent row-lock serialization.
- Existing same-decision retries retain the recorded digest; a later supplied
  digest does not upgrade an omitted-digest decision. The draft derives unknown
  history from absent snapshot and unverified history from snapshot plus absent
  consent digest, making the no-post-decision-initialization invariant essential.
- First submission uses validated frozen days and the existing submitted-at
  anchor. Already-stored deadlines and idempotent submission records are not
  rewritten. Legacy missing snapshots retain the previous fallback behavior.
- Draft downgrade refuses recorded snapshots or consent digests and obtains
  PostgreSQL exclusive table locks before inspection. Actual populated migration
  and concurrency evidence must come from the owner; this review runs no DB.
- UI `645b4c5` echoes the digest paired with the displayed notice on either
  decision. A review-required conflict enters an error state, and explicit
  reload precedes a fresh explicit choice; no automatic consent retry exists.
  It accepts missing/null digest for old-server compatibility. Thus the pure
  contract sentence saying the new UI must never use the legacy fallback needs
  reconciliation with this deliberate old-server behavior.
- The draft differs from the prose contract in timestamp naming, deriving
  evidence rather than persisting `notice_evidence`, and using
  `notice_snapshot_invalid` rather than `notice_snapshot_unavailable`. Owners
  should make the final handoff match the actual wire/storage contract.

## Focused verification

A database-free `tsx` invocation parsed the consent member of
`CandidateDataExportSchema`: the original synthetic object passed, while the
same object plus the six API notice fields failed with `unrecognized_keys` for
all six fields. This is a targeted reproduction of finding 1, not a full-suite
result. No pure-module suite, database fixture, or browser server was started.

A second targeted parse against the evolving `iopsych-notice-wire-compat`
contract accepted that same additive legacy-unknown export. Its uncommitted
proxy changes forward only explicit capability `1` for candidate GET/consent,
and its client advertises that capability on those calls. The newer API draft
also adds complete-or-null, provenance and digest checks plus post-decision
initialization guards in migrations and metadata-created databases. These are
observed fixes pending final revision confirmation, not final acceptance.

Candidate capability negotiation protects already-open old candidate clients.
The draft privacy export remains unconditional, so already-open old strict
admin clients still need a reload/rollout strategy even after the updated export
parser ships. This is distinct from the resolved updated-client parsing defect.

## Final checkpoint assessment

All four revisions listed above were reviewed after their owners committed.
The initial integration blockers are resolved in the API and wire/client
checkpoints. Coordinator integration and a combined browser/runtime check remain
separate from this read-only review. No broader provider reconciliation was
reviewed or claimed.

### API checkpoint resolution

At `1aec1596d9c95625486903ddeaa6b45490f546e8`, finding 2 is resolved by
complete/null, origin/digest constraints and matching migration/metadata
immutability triggers that also forbid post-decision initialization. Finding 3
is resolved at the candidate API boundary by explicit capability opt-in and
exact legacy-response-key tests. The mixed GET/legacy POST PostgreSQL case is
present in the final revision and asserts identical content/digest without
fabricated client digest evidence.

The owner reports 105 passing focused tests, zero skips, including isolated
PostgreSQL populated migration and race tests, with Ruff and scoped mypy passing.
These results are attributed to `docs/implementation/notice-snapshot-api.md`;
this reviewer inspected the tests and implementation but did not rerun DB or
full suites. No additional blocking API correctness defect was found in the
committed checkpoint. Retained-copy/contact limitations and client integration
remain as described above.

### Wire/client checkpoint resolution

At `f42fef868452b9c281cbc1a92ace8360439f60a3`, findings 1 and 5 are resolved:
the client advertises capability on landing/consent, the proxy forwards only
that explicit value on those paths, and the export parser retains all six new
fields while accepting legacy exports. Proxy tests check that cookies,
authorization and unrelated headers are not forwarded, that unrelated candidate
paths do not opt in, and that no-store behavior is retained. Export tests use
the actual client and download payload, not just a permissive mock.

The wire owner reports 80 passing focused tests, web typecheck and scoped ESLint
passing; this reviewer inspected those tests and independently reproduced the
previously failing export parse successfully against the final schema content.
Candidate UI `645b4c5` requires a manual reload and new explicit choice after a
notice conflict. No automatic consent path was found.

Remaining caveats are the old admin-tab reload/rollout strategy, retained notice
copy/contact handling and external privacy/content approval, and reconciliation
of the earlier prose contract with the final timestamp/error/evidence names and
deliberate old-server fallback. These do not authorize changing product policy
or rewriting historical evidence. Existing stored deadlines remain unchanged.

### Race cases for final evidence

| Interleaving | Expected invariant and inspected draft path |
| --- | --- |
| Two first GETs under different configuration | First invite lock holder freezes once; the second refreshes and returns that snapshot. |
| Digest-less POST before first GET | POST freezes `legacy_decision` and persists unverified consent; later GET does not relabel provenance. |
| First GET before digest-less POST | GET freezes `first_presented`; POST retains it but does not claim digest evidence. |
| Consent versus decline | Invite lock serializes the consent lookup; only the first terminal decision persists. |
| Matching retry after omitted digest | Existing consent row is reused without assigning a presented digest. |
| Stale digest against undecided legacy row | No first snapshot is written by the rejected supplied-digest request. |
| Same issuance key across configuration change | Original delivery/request digest resolves to the original invite and frozen notice. |
| Submission retry after retention change | Existing assessment is returned before new deadline construction. |
| Export versus anonymization | Existing privacy service assessment locking is unchanged; notice data does not add an unlocked separate mutable record. |

These are code-path observations, not independently executed concurrency tests.
The initial new API tests cover sequential service behavior, including altered
settings, legacy branches and stale-digest audit counts; those tests alone do
not establish PostgreSQL locking or migrated-schema guarantees.
