# Corrected frozen regression checkpoint

Date: November 4, 2026, approximately 23:03–23:07 UTC. Tested revision:
**`58eaad8d75302425af522e6f09b0c5e60ff13cce`**, unchanged throughout execution.
Worktree: `iopsych-regression-second`; task `task_b60b4cec1430`, dispatch
`ctx_012e05c67073`.

**Checkpoint completed; combined acceptance fails only at Python lint.**
Formatting, TypeScript/Python typing, all broad unit tests, coverage gates,
schema generation/drift, and production build pass. All eleven opt-in skips
pass in isolated follow-ups. This report is the only committed change.

## Setup and isolation

Read the final implementation plan, web AGENTS guidance, and prior
`docs/implementation/current-regression.md` command map. No root or ancestor
AGENTS file was present. Existing local dependencies were used without installs:
Node `v24.21.0`, npm `11.19.0`, Python `3.12.16`, pytest `9.1.1`, Next `16.4.1`.
The initial working tree was clean. No model/session setting was changed.

Broad commands removed ambient `DATABASE_URL`, `TEST_POSTGRES_URL`,
`READINESS_TEST_DATABASE_URL`, `IOPSYCH_TEST_LOCAL_MAILPIT`, and `PYTEST_ADDOPTS`.
No test deselections, threshold changes, suppressions, app edits, dependency
edits, or guard bypasses were used. The launcher used allocated port 8113 and
the stalled-handshake test used allocated port 8133.

After checking that the allocated ports were free, created only these fresh
containers, each labelled `iopsych.owner=task_b60b4cec1430`:

- `iopsych-corrected-regression-58eaad8`: numeric loopback 5571,
  database/user `iopsych_regression`, image `postgres:16-alpine`.
- `iopsych-corrected-readiness-58eaad8`: numeric loopback 5573,
  database/user `iopsych_readiness`, image `postgres:16-alpine`.
- `iopsych-corrected-mail-58eaad8`: numeric loopback 1139/8139,
  image `axllent/mailpit:v1.27.10`, no relay or forwarding configured.

Both databases used tmpfs data and a disposable synthetic-only password.
Inspected fixture guards before execution: assignment upgrades restrict the
port/database and loopback URL, report/export fixtures own unique schemas,
and readiness requires the allocated 5573 database. Follow-ups supplied explicit
owned URLs; no existing database state was used or reset. Both databases were
ready before execution. Afterwards, SQL inspection found only `public` among
non-system schemas in each owned database. Verified owner labels and removed
all three containers. Protected 3000/8001/8000/5432 and browser runtime 3116
were untouched.

## Canonical checkpoint

Raw local logs: `/tmp/iopsych-regression-corrected-58eaad8/`, containing
`check.log`, `typecheck.log`, `unit.log`, `build.log`, `schema.log`,
`postgres.log`, `readiness.log`, and `mailpit.log`.

Each broad stage ran once. `npm run check` completed both formatting stages
and JS lint, then stopped at Ruff. Its remaining typecheck and test stages
were run individually. No full-suite rerun was performed.

| Command | Result |
| --- | --- |
| `npm run check` | Exit 1: formatting passes (116 Python files already formatted), JS lint passes, Ruff fails four I001 errors. |
| `npm run typecheck` | Exit 0: web/shared TypeScript passes; mypy reports no issues in 104 source files. |
| `npm run test` | Exit 0: all broad unit and coverage gates pass; counts below. |
| `npm run schemas --workspace @iopsych/shared` | Exit 0. |
| `git diff --exit-code -- packages/shared/schemas packages/shared/definitions` | Exit 0: no generated schema/definition drift. |
| `npm run build` | Exit 0: shared TypeScript and Next webpack production build pass, 15 listed routes, no build warning. |

| Test layer | Broad-run result |
| --- | --- |
| Web | 33 files, 371 passed; statements 93.73% (1272/1357), branches 88.96% (967/1087), functions 93.27% (333/357), lines 95.43% (1191/1248). |
| Shared TypeScript | 3 files, 99 passed. |
| Python contracts | 93 passed in 0.49 s; 483 statements, zero missing, required coverage 100%. |
| API | 851 collected; 840 passed, zero failed, 11 skipped, 1 warning in 26.97 s; 3092 statements, zero missing, required coverage 100%. |

The 32 telemetry cases pass in the broad run, including the previously failing
interaction. Coverage additions are included; the prior missing report/trace/
telemetry lines no longer fail the API gate.

## Exact remaining failures

Ruff I001 reports import ordering in:

- `apps/api/alembic/env.py:3`
- `apps/api/alembic/versions/20261104_0009_invitation_deliveries.py:7`
- `apps/api/tests/test_database_migrations.py:3`
- `apps/api/tests/test_telemetry.py:3`

Escalated as `msg_a3eeb34b9a96`. Coordinator confirmed in
`msg_31f3797f420b` that root canonical Ruff and app-directory Ruff infer the
local Alembic namespace differently, and reported a separate correction to pin
Alembic as third-party and normalize imports. That later correction was not
applied or verified here; this frozen snapshot remains failed at lint.

## Exact skips and targeted follow-ups

All commands below use `.venv/bin/python -m pytest`, clear ambient
`DATABASE_URL` and `PYTEST_ADDOPTS`, and append `--no-cov -ra`. Narrow runs do
not replace the independently passing broad coverage gate.

1. Explicit `TEST_POSTGRES_URL` points to the fresh numeric-loopback
   `5571/iopsych_regression` database. Targets:
   `apps/api/tests/test_reports_postgres.py` (two cases),
   `apps/api/tests/test_privacy_export_postgres.py` (three cases),
   `apps/api/tests/test_assignment_upgrade.py::test_populated_upgrade_preserves_assignments_and_original_interpretation[postgresql]`,
   and `apps/api/tests/test_report_trace.py::test_postgres_trace_and_deletion_serialize_in_both_orders`.
   **Exit 0: 7 passed, zero skipped, 1 warning in 4.10 s.**
2. Explicit `READINESS_TEST_DATABASE_URL` points to the fresh numeric-loopback
   `5573/iopsych_readiness` database. Targets in
   `apps/api/tests/test_database_readiness.py`:
   `test_postgres_statement_and_pool_deadlines`, `test_postgres_lock_deadline`,
   and `test_postgres_actual_migrations_and_search_path`.
   **Exit 0: 3 passed, zero skipped, 1 warning in 1.36 s.**
3. Set `IOPSYCH_TEST_LOCAL_MAILPIT=1`; target
   `apps/api/tests/test_local_invitation_delivery.py::test_real_mailpit_capture`.
   **Exit 0: 1 passed, zero skipped/warnings in 0.11 s.**

These eleven cases account for every broad-run skip: one assignment upgrade,
three readiness, one local mail sink, three privacy export, one report trace,
and two report concurrency/retention cases. Broad execution omitted their
explicit opt-in environment variables; targeted evidence is separate from the
unchanged broad skip count. The API broad run and the two PostgreSQL groups
emit one StarletteDeprecationWarning each about httpx test-client support being
deprecated in favor of httpx2; no warning failed execution.

## Handoff limits and integrity

Runtime-queue and incoming account work are **not on this snapshot** and are
not covered by these results. No browser runtime, HTTPS staging, hosted CI,
security rescan, public deployment, push, purchase, external provider, real
email, production secret, existing database reset, or scientific/product
approval was exercised. This checkpoint does not establish release readiness.

Next generated the expected `apps/web/next-env.d.ts` change from `.next/dev/types`
to `.next/types`; inspected and restored that generated-only delta to HEAD.
The root lock SHA-256 is
`3955c758b434f3989811f004daef3fc2826e865bd2fcd368fa26621c23310189`;
the browser lock SHA-256 is
`c32a4d9a9ad60fdce78c598abb8b87db17ee5a287c96984781a2e5de9824d01f`.
Application code and dependencies remain unchanged. Coordinator owns integration
and migration changes. Next eligible verification is the focused Ruff correction
on its actual integrated revision, followed by verification appropriate to any
newly integrated runtime/account changes.
