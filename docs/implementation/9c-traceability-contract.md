# 9C item-level traceability contract proposal

Prepared 2026-11-04 against `c20b3ed` in the dedicated
`AbhiNutakki/iopsych-report-traceability` worktree. This is a bounded design
handoff, not implemented API/UI behavior, full 9C acceptance, or scientific
approval. Only this document changes. No migrations, dependency files, shared
contracts, progress ledger, runtime services, or ports were changed.

Inputs: `final-implementation-plan.md` phase 9, `mvp-spec.md` sections 5–7 and
FR-07, `finish.md` tasks 2/7/8, `docs/implementation/progress.md`, and
`docs/implementation/6b-decisions.md`. The only discovered repository AGENTS
file is `apps/web/AGENTS.md`; its Next.js documentation requirement applies
before future UI code changes. The backend 6C contract was read in the sibling
`iopsych-6c-versions/docs/implementation/6c-contract.md` worktree (base
`4638236`, coordinator-agreed, still uncommitted when inspected). Its registry
implementation was also inspected read-only; these observations do not assert 6C
integration or acceptance.

## Current evidence chain

Paths below are relative to repository root; named symbols identify exact logic.

| Stage            | Source and persisted fields                                                                                                                                | Actual behavior / gap                                                                                                                                                                                                                                                                                                                              |
| ---------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Source content   | `packages/shared/definitions/v1/pilot-assessment.json`; Python `assessment.py:AssessmentDefinition`, TS `assessment.ts`                                    | Draft `work-preferences-pilot` / `1.0.0`: six blocks, four distinct constructs per block, four exposures per construct, globally unique item IDs. Statements and construct assignment are versioned.                                                                                                                                               |
| Submission       | `apps/api/app/invitations/service.py:CandidateInvitationService.submit` (method `submit`); `apps/api/app/database/models.py:Assessment`                    | Consent-gated submission persists `definition_json`, canonical `responses_json`, `scores_json`; same-response retry returns existing assessment. Baseline loads the current pilot file; 6C instead scores the pinned assignment and copies its definition into assessment storage.                                                                 |
| Scoring          | `packages/shared/python/iopsych_contracts/assessment.py:score_assessment`; TS `packages/shared/src/assessment.ts:scoreAssessment`                          | Every block must be answered or explicitly skipped. Most = +1, least = −1, other two = 0. Every item in an answered block counts as answered, including unselected items. A skipped block adds one skipped exposure for each of its four constructs; it is not a global skip for all six constructs.                                               |
| Construct output | `AssessmentScoreResult.construct_scores` / `CandidateConstructScore` in both languages                                                                     | Retains definition ID/version, scoring version, per-construct raw score, rating, confidence and assigned/answered/skipped counts. Does not retain item IDs or statement-level contributions in the score object.                                                                                                                                   |
| Matching         | Python `matching.py:match_construct`, `match_role_profile`; TS `matching.ts`                                                                               | Algorithm `1.0.0`; structure comparison target = `6 - role.rating`; all others use role rating. Absolute distance 0–1 aligned, 2 worth discussing, 3–4 potential friction. Lower of role/candidate confidence applies; low confidence yields insufficient evidence before distance classification. Pure matcher also guards unapproved input.      |
| Generation       | `apps/api/app/reports/service.py:ReportService.generate`                                                                                                   | API requires submitted, non-anonymized, affirmative-consent assessment and invitation-linked approved/superseded profile with approval attribution; tenant-scoped locks. Uses persisted scores and approved role ratings/rationale/quotes. Stores `AlignmentReport.result_json`, plus per-item explanations/questions; generation audit is atomic. |
| Stored report    | `MatchingResult`, `AlignmentExplanation`, `RoleEvidenceSummary`, `CandidateResponseSummary`                                                                | Preserves six independent classifications, confidence, role rationale/quotes, raw score/counts/rating, comparison target/rating, rule ID/description/difference, uncertainty, question IDs/text, and input versions. No block IDs, statements, selections, weights or rating/confidence thresholds.                                                |
| Read and UI      | `reports/service.py:read/_response`; `apps/web/lib/report-contracts.ts:ReportSchema`; `apps/web/app/reports/report-detail.tsx:ReportDetail/EvidenceDrawer` | Read returns stored result, not a fresh match. UI shows aggregate evidence, inverse arithmetic, source/version references and question IDs. Drawer cannot trace a rating to individual items. Labels/prompts currently come from the imported current construct dictionary, a future historical-label drift risk.                                  |

Baseline report models use a literal `1.0.0` algorithm and strict nested models;
web `ReportSchema` is a `z.strictObject`. Adding even an optional field to an
existing response breaks an old strict client when that field is present. The
internal proxy currently allows `/reports/{id}` but not `/reports/{id}/trace`.

The v1 inclusive raw-score bands are −4..−3 → 1, −2..−1 → 2, 0 → 3, 1..2 → 4,
3..4 → 5. Candidate confidence counts skipped exposures per construct: 0 high, 1
medium, 2+ low. These are evidence-completeness categories, not measured
probabilities or instrument validity. Zero from an unselected item and zero from
a skipped item have different completeness effects.

## Minimal additive interface: separate read-only resource

Propose `GET /v1/reports/{report_id}/trace`, with a separate strict
`ReportTraceV1` schema. Leave GET/POST report envelopes, shared
`MatchingResult`, stored report JSON, classification, ordering, questions and
algorithm version unchanged. The trace contract version is independent of the
matching algorithm. This proposal requires coordinator contract allocation
before implementation.

The response contains these exact fields (type notation, not executable JSON):

```ts
type ReportTraceV1 = {
  trace_version: "1.0.0";
  report_id: UUID;
  assessment_id: UUID;
  role_profile_id: UUID;
  role_profile_version: PositiveInteger;
  algorithm_version: "1.0.0";
  assessment_definition_id: string;
  assessment_definition_version: string;
  scoring_version: string;
  definition_sha256: string; // 64 lowercase hexadecimal characters
  source: "stored_assessment";
  scoring: ScoringConfig; // exact historical definition.scoring, once per response
  constructs: ConstructTrace[]; // exactly six, canonical construct order
};
type ConstructTrace = {
  construct_key: ConstructKey;
  items: ItemTrace[]; // exactly four; historical block position order
  rating_threshold: RatingThreshold; // exact inclusive band containing stored raw score
  confidence_rule: CandidateConfidenceRule; // exact historical rule for skipped count
  question_selection: {
    algorithm_version: "1.0.0";
    construct_key: ConstructKey;
    classification: AlignmentClassification;
    primary_question_id: string;
    follow_up_question_id: string;
  };
};
type ItemTrace = {
  block_id: string;
  block_position: 1 | 2 | 3 | 4 | 5 | 6;
  item_id: string;
  statement: string;
  choice: "most_like" | "least_like" | "not_selected" | "block_skipped";
  most_like_item_id: string | null;
  least_like_item_id: string | null;
  contribution: -1 | 0 | 1;
};
```

`ScoringConfig`, `RatingThreshold`, and `CandidateConfidenceRule` mean the
existing historical JSON shapes in `scoring_config.py` / `scoring-config.ts`:
threshold has `rating`, `minimum_raw_score`, `maximum_raw_score`; confidence
rule has `level`, `minimum_skipped_items`, `maximum_skipped_items` (nullable).
No new scoring policy is introduced. Use existing construct/classification
enums.

Each row includes the selections of its containing block, even when this row's
item was not selected. Their IDs resolve to other rows in the same bounded
24-item response, exposing forced-choice context without copying statements
repeatedly. A skipped block has both selection IDs null and contribution zero;
unselected answered items have nonnull selections and contribution zero. All
four exposures must be included, not only nonzero contributions. The block
position is definition order, not a claim about randomized on-screen order.

Do not duplicate role rationale, score summaries, applied-rule prose or question
text in this endpoint: join by report ID and construct key to the unchanged
stored report. Question provenance identifies the historical deterministic
construct/classification selection and stored IDs; it does not certify actual
external review. The library's `review_status = approved` string is not evidence
of accountable I-O approval. No LLM or new prose generation is needed.

## Historical resolution, validation and access

Implement a retained trace builder keyed by supported
definition/scoring/algorithm versions. Follow 6C's retained `SCORERS`,
`REPORT_READERS`, `read_assignment`, `read_scores`, and `read_report` boundaries
after integration; never use the current pilot import as a fallback. For v1,
exact content must match the frozen 6C legacy definition. Use 6C's canonical
hash (sorted keys, compact JSON, unescaped Unicode, UTF-8 SHA-256); this is
integrity identification, not a signature.

1. Resolve report/profile/assessment in the authenticated organization, using
   existing report roles (recruiter, hiring manager, admin), before any trace
   construction. Retain the existing anonymization denial. This is an internal
   report resource; candidate bearer tokens do not grant access.
2. Read the saved report using its stored algorithm. Validate the assessment
   definition, complete responses, scores and report version identifiers agree;
   match assessment/profile IDs to the report. For pinned records, verify the
   assignment checksum and definition agree too. Recognized pre-6C history may
   use its exact stored frozen v1 definition without inventing a new assignment.
3. Resolve block/item IDs only within that historical definition. Validate
   distinct selections, one response per block and exact item membership. Build
   contribution/count explanations using its scoring config. A retained scorer
   may verify equality with stored scores in memory; never write its output or
   rematch the report. Compare all six computed summaries with persisted scores
   and report candidate summaries. Reject inconsistency rather than repairing
   it.
4. Take role rationale/quotes, rule, classification, uncertainty and questions
   from the saved report. Do not fetch current profile evidence or current
   question text to replace history. Verify question provenance using the
   retained v1 selector when supported; never imply new scientific approval.
5. Return `Cache-Control: no-store` and audit `alignment_report.trace_read`
   against the report ID. Do not log response bodies, statements, choices,
   credentials or emails. Read related source records in a consistent
   transaction and coordinate with privacy deletion locking, so no partial trace
   escapes a concurrent anonymization transaction.

Proposed failure contract: existing 401/403 auth behavior; tenant-hidden 404;
existing 410 `candidate_data_anonymized` when the row remains (normally privacy
deletion removes the report, yielding 404); 409 `unsupported_report_version` or
`unsupported_assessment_version` for unknown versions; 409
`report_trace_unavailable` for absent legacy inputs; 409
`report_trace_inconsistent` for invalid/hash-mismatched or contradictory inputs.
Errors contain generic details, not the source payload. Do not return a partial
trace, guess statements or substitute current definitions. An otherwise readable
historical report remains readable when only its new trace fails. Trace errors
must not weaken existing report-reader validation.

No database migration/backfill or new stored candidate-data copy is needed:
construct the bounded response on demand from existing assessment snapshots.
Existing anonymization clears definition/responses/scores and deletes reports;
this endpoint must respect that lifecycle. Any future trace persistence requires
separate privacy/export/retention allocation. Historical expiry/retirement alone
must not trigger current new-assignment eligibility gates or block a permitted
historical report read. No new withdrawal or access policy is selected here.

## Concrete backend/UI split

**Backend slice, independently implementable after coordinator allocation and 6C
integration:** own new `apps/api/app/reports/trace.py`, trace response schema,
report route integration, and `apps/api/tests/test_report_trace.py`. Provide the
versioned pure builder, source cross-checks and protected endpoint above. Reuse
6C registry rather than editing it concurrently. Keep matching algorithms,
shared report schemas, migrations and generation untouched. Return exact frozen
synthetic JSON fixtures for UI consumption. Backend rollout is compatible with
old UI because its existing responses are unchanged.

**UI slice after wire-schema agreement:** own
`apps/web/lib/report-trace-contracts.ts`, a trace client helper, narrow GET
proxy allowlist addition in `apps/web/app/api/internal/[...path]/route.ts`, and
`report-detail.tsx` plus focused tests. Coordinate `api-client.ts`/proxy
ownership with other workers first. Existing report parser remains unchanged.
Fetch trace when the evidence drawer opens, validate the whole strict envelope
and IDs, then show only the selected construct's four rows with block/item
references, statements, choices, signed contributions, raw total, inclusive
threshold and completeness rule. Show the stored role rationale and matching
arithmetic beside it. Use a retained v1 construct-label/prompt dictionary; never
silently change historical scale meaning when future definitions are introduced.

Expose loading, retry and unavailable states inside the existing accessible
modal. Aborted/stale fetches must not show another report's evidence. Keep focus
restoration, Escape and native-dialog behavior; use semantic table/list headings
and text choice labels. For unavailable/unsupported trace, retain the old report
with “Item-level evidence unavailable for this saved report” and no fabricated
rows. Distinguish backend rollout 404 from historical absence where possible;
401/403/410 should trigger existing auth/unavailable handling and clear
sensitive trace state. Never persist trace in browser storage. Retain
responsible-use copy and clearly describe candidate confidence as completeness,
not a probability.

**Small first dispatch:** pure v1 trace builder + frozen complete/skipped
fixture checks, with no endpoint or UI edits. This can be reviewed independently
without resolving structure policy. Then protected endpoint, then UI against
accepted fixtures. Engineering contract allocation is required; this document
does not authorize shared-file edits. Full 9C's matching-correction acceptance
stays gated.

## Compatibility fixtures and exact assertions

Use synthetic frozen v1 definitions. Baseline fixture selects item index 0 most
and index 1 least in every block (indices refer to stored definition order). The
tuples below are `(raw, rating, confidence, skipped count)`:

| Fixture                        | Expected result / assertion                                                                                                                                                                                                                                           |
| ------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Complete                       | Autonomy `(2,4,high,0)`, structure `(2,4,high,0)`, ambiguity `(0,3,high,0)`, collaboration `(-2,2,high,0)`, mastery `(0,3,high,0)`, pace `(-2,2,high,0)`. All have assigned=answered=4; 24 trace rows.                                                                |
| Skip block-1                   | Autonomy `(1,4,medium,1)`, structure `(2,4,medium,1)`, collaboration `(-2,2,medium,1)`, mastery `(1,4,medium,1)`; ambiguity and pace unchanged. `b1-structure` changes from not-selected zero to skipped zero, demonstrating completeness without a raw-score change. |
| Skip block-1 and block-2       | Autonomy `(1,4,low,2)` and mastery `(1,4,low,2)` force insufficient evidence even though rating=4. Structure/collaboration have one skip; ambiguity `(-1,2,medium,1)`, pace `(-1,2,medium,1)`.                                                                        |
| All skipped                    | Every raw score=0, rating=3, candidate confidence=low, assigned=4, answered=0, skipped=4; every report classification insufficient evidence. Never call rating=3 affirmative preference evidence.                                                                     |
| Role low confidence            | Complete candidate responses plus low role confidence: combined low and insufficient evidence, preserving the stored low-confidence rule/questions.                                                                                                                   |
| Threshold boundaries           | Every integer raw score −4..4 maps to the exact five inclusive bands; sum of four contributions equals raw score. Exercise most/least/not-selected/skipped separately.                                                                                                |
| Historical upgrade             | Save v1 report + source snapshots, change current defaults in test only, read same report/trace through retained readers. Stored report JSON, questions, classifications and inverse target remain identical; no assignment-eligibility check on old read.            |
| Missing/unknown/corrupt source | Missing source, unknown version, mismatched hash, response IDs from another block, duplicate/missing blocks, contradictory raw/count/rating or version: typed failure, no current fallback, no data mutation. Original valid report remains readable.                 |
| Auth/privacy                   | Cross-tenant ID hidden, unauthenticated/unauthorized denied, anonymized unavailable, concurrent deletion cannot yield partial source data; no-store and access audit asserted.                                                                                        |
| UI compatibility               | Old report fixture still passes unchanged strict parser; new trace fixture validates independently. Missing trace leaves original evidence usable; failed/stale fetch cannot attach other report data; Escape restores trigger focus.                                 |

Freeze four structure extremes with high role/candidate confidence and approved
profile in both Python and TypeScript. These are historical regression facts,
not endorsement of their interpretation:

| Role R | Candidate C | v1 target `6-R` | Distance | Saved classification |
| ------ | ----------- | --------------- | -------- | -------------------- |
| 1      | 1           | 5               | 4        | potential_friction   |
| 1      | 5           | 5               | 0        | aligned              |
| 5      | 1           | 1               | 0        | aligned              |
| 5      | 5           | 1               | 4        | potential_friction   |

No aggregate score, ranking, sorting by outcomes, inferred ability, or automatic
disposition belongs in these fixtures or UI. Python/TS parity must compare full
matching output, not only labels. New trace fixtures should be language-neutral
inputs/expected JSON; Python builder and TypeScript parser/UI consume the same
fixture once the coordinator allocates fixture ownership.

## Remaining reviewer decisions and evidence

D01 structure meaning remains unresolved: `mvp-spec.md`'s inverse formula
contradicts its high-availability/high-preference prose. A qualified I-O
reviewer and product owner must select and document any changed construct
meaning, thresholds, wording and interpretation. A changed matcher needs a new
algorithm and retained v1 reader; this trace proposal makes no such choice.
Accountable review of assessment statements, confidence wording and interview
questions, and real-participant privacy/access approval remain pending.
Engineering must approve the new wire contract, error taxonomy, fixture
ownership and privacy locking integration before implementation. Provider
decisions are unnecessary for this bounded slice and are not inferred.

Validation on this documentation worktree:

- `.venv/bin/python -m pytest -q packages/shared/python/tests/test_assessment.py packages/shared/python/tests/test_matching.py -o addopts='' -p no:cacheprovider`
  — **78 passed in 0.83s**. Targeted existing domain tests; global coverage gate
  intentionally not invoked. No PostgreSQL or browser acceptance claimed.
- A read-only Python invocation of the existing `score_assessment` against the
  exact complete/block-1/block-1+2 synthetic fixtures confirmed every tuple
  above.
- `npx prettier --check docs/implementation/9c-traceability-contract.md` —
  passed.
- `git diff --check` — passed; only this new document is staged for commit.

These checks establish current behavior, not implementation of the proposed
endpoint or completion of packages 6C/9C. Next eligible work is the bounded pure
builder dispatch after coordinator contract allocation; scientific correction
and full release gates remain open.
