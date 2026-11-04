# Remote structure semantics review receipt

Reviewed integration `b77567c`, remote `646201a` decision/MVP, and semantic change
`c2313fd` in the isolated review worktree. Read the applicable web AGENTS and
accelerated plan. The initial review changed no application files; the coordinator
subsequently expanded ownership to backend compatibility (see addendum below).
Initial collision guidance was sent to lead dispatch
`ctx_9a9c76cc5c41` and coordinator (`msg_d61d75a23677`, `msg_5a32a070bb4a`).

## Decision and adoption boundary

The November 3 repository-owner decision supports direct structure comparison
for new algorithm `2.0.0`: 5/5 and 1/1 align; 1/5 and 5/1 indicate potential
friction, subject to approval/confidence gates. It is product confirmation, not
scientific approval, deployment approval, or authorization for real-candidate use.
Keep v1 inverse target, saved explanations/questions and explicit replay exactly.
Do not rewrite old rows, assignment snapshots, definition hashes, or scores.

## Exact integration collisions

| Location | Required reconciliation |
| --- | --- |
| `apps/api/app/assignments/registry.py` | `MATCHERS["1.0.0"]` currently points at the default matcher: bind explicit v1 before adopting the remote v2 default. Add supported readers with row/payload algorithm equality and target validation. Keep unknown-version failure closed. |
| `apps/api/app/reports/service.py` | Preserve assignment/score validation, privacy serialization locks, trace endpoint and `read_report` checks. Remote whole-file replacement drops these. Select new report algorithm independently from the historical assignment algorithm; preserve definition/scoring/hash validation. Keep per-assessment/profile/algorithm uniqueness and idempotency. |
| Submission discovery in that service | Adopt the remote correlated supported-version lookup, preferring v2 with v1 fallback. Keep one chronological submission row even when both reports exist. Do not merely widen the existing join and duplicate rows. |
| `apps/api/app/reports/trace.py` | Current assignment algorithm equality rejects a v2 report from a valid v1 assignment. Validate the assignment independently; continue checking definition/hash, scoring, raw responses and saved report provenance. Trace must describe the saved report algorithm without rematching it. |
| `apps/api/app/reports/trace_schemas.py` and `apps/web/lib/report-trace-contracts.ts` | Both question selection and report algorithm fields are literal v1. Support v1/v2 there; retain trace schema version `1.0.0` and v1 question-library identity. Report/trace algorithm consistency remains required. |
| `apps/web/lib/candidate-contracts.ts` | Assignment metadata currently permits only v1. If new assignments advertise v2, widen supported assignment metadata too; historical assignments remain unchanged. A v2 report over an old assignment does not itself require rewriting that metadata. |
| Shared TS/Python matching, constructs and generated schemas | Adopt explicit algorithm dispatch and target validation in both languages, current v2 metadata and its package export. Preserve frozen v1 metadata/question library. Contract shape stays v1 while supported matching algorithms expand. |
| `apps/web/app/reports/report-detail.tsx` | Integrate remote available-structure and historical-inverse wording into the current evidence drawer, not by replacing its richer implementation. Display the saved report algorithm and target. |

Remote schema generation adds algorithm-dependent structure targets under
`allOf`; retain that constraint when regenerating. Zod refinements alone are not
automatically a portable JSON Schema guarantee. Check generated schemas against
both runtime readers, including invalid algorithm/target combinations. Keep
definition version, scoring version, matching algorithm, trace contract version,
and question-library version separate.

## Focused verification and handoff

Executed a pure Python check using the existing `.venv`, with
`PYTHONPATH=packages/shared/python`: loaded the frozen legacy fixture directly
from `git show c2313fd:packages/shared/fixtures/v1/matching-result/legacy-structure.json`.
Both integration `MatchingResult` parse/dump and integration v1 matching of its
stored context exactly equal the remote fixture payload. **PASS**. This confirms
the incoming frozen fixture is a valid baseline, not that merged v2 is verified.
No full suite, DB, provider, or production operation was run.

The reconciliation owner's minimum acceptance checks:

- Exact complete frozen-v1 read and explicit replay in TS/Python, including old
  structure classification, explanation and question IDs/text.
- Four shared v2 extremes plus unapproved/low-confidence gates; unchanged
  non-structure behavior and rejection of unknown algorithms or mismatched targets.
- Generated reader-schema acceptance of both versions and rejection of target
  tampering; regeneration preserves v1 definitions and question-library content.
- Pure trace fixture for a v2 report using an immutable v1 assignment, checking
  report and question-selection algorithm v2 while trace/definition/scoring stay
  at their own versions; retain malformed assignment and privacy boundary tests.
- Existing remote API historical-read/separate-v2/idempotency/discovery test
  adapted to the integration assignment fixture, proving unchanged stored v1 and
  a single discovery row. Keep integration tenant, consent, approved-profile,
  anonymization and trace locking checks.
- Web tests for direct v2 wording, historical v1 wording/questions, and both
  trace algorithm values with mismatched report/trace versions rejected.

Implementation and merged-HEAD verification remain with the reconciler and
coordinator. Protect the accelerated plan's final checks; this receipt claims no
scientific validation, full-package completion, or release readiness.

## Authorized implementation addendum

Coordinator message `msg_f9b3659fa3d0` and lead message `msg_bfd7c90bfe41`
expanded this lane to registry, report service, trace/schema and focused tests.
Remote shared semantics were imported as a separate local validation baseline,
`97294b6`; **do not cherry-pick that baseline** because the lead owns remote shared
integration. The compatibility commit following it contains only owned backend
changes, a dedicated pure test module, and this receipt update.

The registry now binds both algorithms explicitly, retaining default assignment
replay and fail-closed content eligibility. Report generation explicitly selects
current v2 after checking frozen assignment/score provenance; no assignment is
rewritten and new assignment metadata remains v1. Discovery prefers supported
v2 then v1 without duplicate submission rows. Trace accepts a distinct supported
report algorithm while retaining all definition/hash/score/source checks and
privacy locks; its schema version remains v1. Historical report reads still use
the row/payload algorithm guard and never call a matcher.

Validation: 26 focused pure compatibility/assignment/historical-trace checks passed
with `--no-cov`; after adding the score-version mismatch assertion, 56 compatibility
and shared Python matching tests passed. The first 12-test focused run passed its
tests but returned failure because default whole-application coverage requires
100%; that coverage gate was not represented as met. Ruff lint/format and diff
checks cover changed backend files. No DB or full-suite run was performed.

Remaining integration responsibilities: adapt/run remote API upgrade/idempotency/
discovery tests against merged assignment fixtures; widen the two frontend trace
algorithm fields; run merged TS/generated-schema checks and privacy/API checks.
The lead may take this lane's complete `reports/service.py` if its independently
merged correlated discovery causes a cherry-pick conflict; it preserves current
integration assignment validation, read guards and trace privacy locking.
