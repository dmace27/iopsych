# 9C additive trace backend evidence

Completed 2026-11-04 in the dedicated `AbhiNutakki/iopsych-trace-backend`
worktree, based on `4c7caf3`. Coordinator approval covers the engineering
interface in `9c-traceability-contract.md`; it is not scientific approval or
full 9C acceptance.

## Changes and integration

- `f5bee77b8e57df94481cad969b85fe7bc3426b66`: retained trace builder, strict
  additive response models, and frozen language-neutral synthetic fixtures.
- `b989af5c35fd3e0faf5dcf95198c72d7e58499b7`: protected endpoint, minimal
  service method, validation refinements, and focused tests.
- Integrate both commits in order, followed by this evidence document. No
  registry, migrations, shared contracts, dependencies, scoring, matching,
  interpretation, or existing report response schemas changed.

`GET /v1/reports/{report_id}/trace` returns the agreed `ReportTraceV1` shape.
Each of six constructs contains all four historical exposures in block-position
order, including zero contributions, exact statements, containing-block choices,
thresholds, completeness rules, and stored question-selection IDs.

The builder requires the exact canonical frozen legacy definition hash,
including when an attacker recomputes a checksum after changing content. Pinned
assignment content/hash/algorithm must agree. Unpinned recognized history can
use its exact stored legacy definition. Retained scoring verifies the complete
response set and persisted scores in memory; all six saved report candidate
summaries and input versions must agree. Question IDs must match the retained v1
selector for the saved classification. Saved prose, questions, classifications
and report JSON are never replaced or rematched. Missing, inconsistent and
unsupported trace inputs fail closed while an otherwise readable historical
report remains readable.

Access uses existing recruiter, hiring-manager and admin authorization, checks
both assessment and report tenant chains, and retains anonymization denial. The
service first locks only `Assessment`, then rereads/locks the report and checks
its invitation/profile linkage. It takes no invitation lock and holds locks
until the existing request middleware commits `alignment_report.trace_read`.
Successful and domain-error endpoint responses carry `Cache-Control: no-store`.
Audit metadata contains method/status/outcome, not statements, choices or source
bodies. A failed required audit returns a generic failure with no trace.

## UI fixtures

Owned directory: `apps/api/tests/fixtures/report_trace/`.

| Fixture pair                                        | Meaning                                                               |
| --------------------------------------------------- | --------------------------------------------------------------------- |
| `complete.source.json`, `complete.trace.json`       | Most item index 0, least index 1 in every frozen block                |
| `skipped.source.json`, `skipped.trace.json`         | Block 1 explicitly skipped                                            |
| `two-skipped.source.json`, `two-skipped.trace.json` | Blocks 1 and 2 skipped; affected constructs have low completeness     |
| `all-skipped.source.json`, `all-skipped.trace.json` | Every block skipped; all stored classifications insufficient evidence |

The `.trace.json` files are exact endpoint-shaped JSON; `.source.json` contains
synthetic inputs and the corresponding saved matching result. IDs are stable
synthetic UUIDs. The UI worker received the absolute directory and fixture
handoff in `msg_f03243b2e702`; the coordinator received the exact commit in
`msg_a38c7b54ce0c`. Fixture contents were not changed after the initial handoff.

## Executed verification

Environment: Python **3.12.16**, PostgreSQL **16.15** (aarch64 Debian), local
Unix Docker socket. Disposable container `iopsych-trace-ctx055f6c` used only
allocated `127.0.0.1:5566`, database/user `iopsych_trace`, synthetic password
and tmpfs data. Postgres image digest:
`sha256:e8a07d2c7579b038938cdba6c539e580e5001caf9ea203d397b5cc83e76bd938`. Tests
reused the existing PostgreSQL fixture, which migrates a fresh UUID schema to
repository head and removes only that owned schema afterward. The disposable
container was removed after verification and port 5566 was no longer listening.
Ports 3000/8000/8001 and existing databases were untouched; no API/web server
was started.

Final code revision tested: `b989af5c35fd3e0faf5dcf95198c72d7e58499b7` (tests
ran on the identical working tree immediately before commit).

```sh
TEST_POSTGRES_URL='postgresql+psycopg://iopsych_trace:synthetic-local-only@127.0.0.1:5566/iopsych_trace' \
PYTHONPATH=apps/api:packages/shared/python \
.venv/bin/python -m pytest -c apps/api/pyproject.toml -o addopts='' -q \
  apps/api/tests/test_report_trace.py apps/api/tests/test_reports.py
```

**61 passed in 1.45s, zero skips:** 47 trace cases and 14 existing report cases.
This targeted run explicitly disables the repository-wide coverage gate; it is
not a full-suite or coverage-acceptance result.

Coverage includes exact frozen fixture equality; all 24 rows; most/least/
unselected/skipped choices; unchanged raw zero with changed completeness; all
nine reachable raw-score threshold boundaries; low role confidence; all-skipped
insufficient evidence; content tampering and recomputed hashes;
invalid/cross-block selections; duplicate, missing and unknown responses;
persisted score/report summary disagreement; question-ID mismatch;
missing/unknown historical inputs; unpinned history; strict extra-field
rejection; all permitted internal roles; cross-tenant/missing resources; invalid
tenant claims and candidate bearer tokens; anonymization; sensitive-data-free
audit metadata; audit failure; and unchanged existing report reads after trace
failures.

The PostgreSQL case executes **both real race orders** and queries
`pg_blocking_pids` to establish actual lock contention:

1. Trace pauses at audit staging while its transaction remains open; deletion
   blocks until the audit can commit. Trace returns a complete validated result,
   deletion removes the report, and subsequent trace reads return 404.
2. Deletion pauses after obtaining the assessment lock; the trace blocks. After
   deletion commits, the waiting trace returns 404/410 without evidence and the
   report is absent. No partial trace or deadlock occurred.

```sh
MYPYPATH=apps/api:packages/shared/python .venv/bin/mypy \
  --config-file apps/api/pyproject.toml --follow-imports=silent \
  apps/api/app/reports/trace.py apps/api/app/reports/trace_schemas.py \
  apps/api/app/reports/router.py apps/api/app/reports/service.py

.venv/bin/ruff check apps/api/app/reports/{trace,trace_schemas,router,service}.py \
  apps/api/tests/test_report_trace.py
.venv/bin/ruff format --check \
  apps/api/app/reports/{trace,trace_schemas,router,service}.py \
  apps/api/tests/test_report_trace.py
git diff --check
```

All passed: mypy reports no issues in four source files, Ruff passes, and all
five Python files are formatted. Initial test development caught missing fixture
imports and corrected a tenant-claim negative assertion to the existing 401
behavior; neither is an outstanding failure.

## Remaining gates

Coordinator integration and combined UI/backend verification remain. The
separately owned registry exact-content fix and privacy-read changes were not
edited or cherry-picked here. No full suite, browser run, hosted deployment,
external provider, scientific review or real-participant acceptance is claimed.
The existing interpretation/structure decision remains unchanged and gated.
