# Frozen current regression checkpoint

Date: November 4, 2026, approximately 22:51–22:57 UTC. Tested revision:
**`e6a39f4d0c92776b7e188a62fc63a734b2e38a51`**, unchanged throughout execution.
Worktree: `iopsych-current-regression`; task `task_bb6f049a629c`, dispatch
`ctx_3848fc7fba6d`.

**Checkpoint completed; combined acceptance fails.** Formatting, Python lint,
Python typing, telemetry tests, and API coverage fail at this frozen revision.
All eleven broad-run opt-in skips passed in targeted follow-ups. This document
is the only committed change; no application, dependency, test, migration, or
product/scientific approval changes were made. Coordinator corrections on later
revisions are not verified by this report.

## Setup and isolation

- Read `final-implementation-plan.md`, `mvp-spec.md`, `finish.md`, and the web
  `AGENTS.md`; no root or ancestor `AGENTS.md` was present. Existing saved
  `node_modules` and `.venv` were used, without reinstalling dependencies.
- Node `v24.21.0`, npm `11.19.0`, Python `3.12.16`, pytest `9.1.1`, Next.js
  `16.4.1`; initial git working tree clean. No model setting was toggled.
- Root lock SHA-256 remained
  `3955c758b434f3989811f004daef3fc2826e865bd2fcd368fa26621c23310189`;
  browser lock remained
  `c32a4d9a9ad60fdce78c598abb8b87db17ee5a287c96984781a2e5de9824d01f`.
- Broad commands removed ambient `DATABASE_URL`, `TEST_POSTGRES_URL`, and SMTP
  opt-in configuration. PostgreSQL was used only in targeted invocations with
  explicit synthetic URLs. No default database was used.
- Inspected upgrade, report, export, and readiness fixture guards before
  targeted execution. Upgrade accepts numeric loopback and the assigned
  `5571/iopsych_regression`, with no URL query; report/export fixtures own UUID
  schemas. Readiness enforces `127.0.0.1:5573/iopsych_readiness`.
- Docker context `desktop-linux`; created only these fresh owned containers:
  `iopsych-current-regression-e6a39f4` (loopback 5571),
  `iopsych-current-readiness-e6a39f4` (loopback 5573), and
  `iopsych-current-regression-mail-e6a39f4` (loopback 1139/8139).
  Both PostgreSQL containers used tmpfs data and database-matching users;
  password `synthetic-local-only` was created solely for these disposable tests.
  PostgreSQL image: `postgres:16-alpine`, digest
  `sha256:721873c34ceb9f8d8fc265984940dc982404c105f19ad51be9fdc5970a6080ea`.
  Mailpit: `axllent/mailpit:v1.27.10`, digest
  `sha256:b1f1be18af530d939a11ee8820b379e0c88eeec204d904bfad68862adced3a5a`;
  no relay, forwarding, or persistent volume configured.
- Coordinator explicitly allocated 8113/1139/8139 in `msg_e63078c360a5`,
  5573 in `msg_b8fa965f6ff9`, and 8133 in `msg_2b81c24ca272`.
  Preflight found no listeners on newly assigned database/mail ports.
  The launcher used 8113; the synthetic stalled handshake used 8133.
- Post-test SQL inspection found only `public` among non-system schemas in both
  owned databases. All three owned containers were removed. Protected
  3000/8001/8000/5432 and browser runtime 3116 were untouched.

## Commands and results

Raw local logs: `/tmp/iopsych-current-regression-e6a39f4/` with `check.log`,
`format-api.log`, `lint.log`, `typecheck.log`, `unit.log`, `schema.log`,
`schema-diff.log`, `build.log`, `postgres.log`, `trace-postgres.log`,
`readiness-postgres.log`, and `mailpit.log`. This document is durable evidence;
`results.json` records timings for the main stages.

Each broad stage ran once. `npm run check` stopped at formatting; its remaining
lint/type/unit stages were then invoked individually, as the coordinator
requested, without repeating the full suite. The environment included
`PYTEST_ADDOPTS='-ra --deselect=apps/api/tests/test_launcher.py::test_actual_launcher_dotenv_and_exported_overrides'`
from the initial port restriction. That selector did not deselect the launcher:
all 559 API items ran or skipped, and the launcher passed after its port was
allocated. No launcher rerun was needed.

| Command | Result |
| --- | --- |
| `npm run check` | Exit 1, 1.56 s; Prettier fails four source fixtures. Later aggregate stages not reached. |
| `npm run format:check:api` | Exit 0; 107 files already formatted. |
| `npm run lint` | Exit 1, 7.91 s; JS ESLint passes, Ruff reports three I001 errors. |
| `npm run typecheck` | Exit 1, 17.99 s; web/shared TypeScript passes, mypy reports ten errors in three files, 96 files checked. |
| `npm run test` | Exit 1, 137.18 s; counts and coverage below. |
| `npm run schemas --workspace @iopsych/shared` | Exit 0, 0.78 s. |
| `git diff --exit-code -- packages/shared/schemas packages/shared/definitions` | Exit 0; no generated schema/definition drift. |
| `npm run build` | Exit 0, 12.52 s; shared build and Next.js webpack production build pass, 14 listed routes, no build warning. |

| Test layer | Broad-run result |
| --- | --- |
| Web | 28 files, 283 passed; statements 92.85% (1065/1147), branches 88.45% (789/892), functions 93.44% (285/305), lines 94.42% (1000/1059). |
| Shared TypeScript | 3 files, 99 passed. |
| Python contracts | 93 passed in 2.28 s, required coverage 100.00%. |
| API | 559 collected; 529 passed, 19 failed, 11 skipped, 1 warning, 99.46 s; required 100% coverage fails at 99.82%, 2793 statements, 5 missing. |

## Exact failures and follow-up ownership

1. **Fixture formatting / integration owner:** Prettier rejects
   `apps/api/tests/fixtures/report_trace/all-skipped.source.json`,
   `complete.source.json`, `skipped.source.json`, and `two-skipped.source.json`.
   Escalated in `msg_a419bb8f1d81`; coordinator reported a later correction.
   Frozen result remains failed.
2. **Python import order / integration owner:** Ruff I001 at line 3 of
   `apps/api/tests/test_assignment_upgrade.py`, `test_database_readiness.py`,
   and `test_privacy_export_postgres.py`, concerning `alembic.command` import
   placement. Escalated in `msg_7585590d4d55`; coordinator reported a later fix.
3. **Test typing owner:** mypy errors in `test_extraction_bounds.py` at 78
   (Callable argument mismatch), 196 (`addinfourl.msg`), 327/328/342
   (`RoleProfileResponse` compared to literal `draft`), and 347 (`read` override
   accepting `int` instead of `int | None`); `test_report_trace.py` at 46/243
   (`no-any-return`); `test_assignment_upgrade_guards.py` at 63/77 (fixture
   `__wrapped__` attribute). Escalated in `msg_e69c41b9917a`.
4. **Telemetry/integration owner:** all 19 API failures are in
   `test_telemetry.py`: `test_server_owned_id_and_sensitive_inputs` (4 cases),
   `test_actual_candidate_and_unknown_routes` (3),
   `test_500_is_correlated_once_without_exception_text` (1),
   `test_early_limits_correlated_before_routing` (2),
   `test_incomplete_requests_never_claim_success` (4),
   `test_route_snapshot_and_header_overwrite` (1), `test_duration_is_bounded`
   (3), and `test_included_prefix_template` (1). Captured telemetry records
   are empty: first four assert `0 == 2`; remaining cases fail unpacking one
   expected record from zero. Escalated in `msg_2ffa0c9be8c8`.
   Static suspect, not independently reproduced here: `alembic/env.py:15`
   calls `fileConfig` with its default existing-logger disabling behavior;
   telemetry initializes a module logger and sets its level without resetting
   `disabled`. Sent to coordinator in `msg_234649b913f2`.
5. **Coverage owners:** missing lines are `app/reports/service.py:219,228`,
   `app/reports/trace.py:49,69`, and `app/runtime/telemetry.py:41`.
   Targeted runs below use `--no-cov` for narrow verification and do not replace
   or waive the failed broad coverage gate.

The API broad run and two PostgreSQL follow-ups emit one
`StarletteDeprecationWarning` each: httpx support in `starlette.testclient` is
deprecated in favor of httpx2. This warning did not fail tests.

## Targeted opt-in verification

Every command below clears ambient `DATABASE_URL` and `PYTEST_ADDOPTS`, runs
`.venv/bin/python -m pytest`, and appends `--no-cov -ra`. No guard bypass or
application edits were used.

1. Set `TEST_POSTGRES_URL=postgresql+psycopg://iopsych_regression:synthetic-local-only@127.0.0.1:5571/iopsych_regression`;
   targets `apps/api/tests/test_reports_postgres.py`,
   `apps/api/tests/test_privacy_export_postgres.py`, and
   `apps/api/tests/test_assignment_upgrade.py::test_populated_upgrade_preserves_assignments_and_original_interpretation[postgresql]`.
   **Exit 0: 6 passed, zero skips, 1 warning, 2.49 s.** Covers reports/submission,
   export/erasure ordering, and populated historical-assignment upgrade.
2. Same explicit 5571 URL; target
   `apps/api/tests/test_report_trace.py::test_postgres_trace_and_deletion_serialize_in_both_orders`.
   **Exit 0: 1 passed, zero skips/warnings, 0.90 s.**
3. Set `READINESS_TEST_DATABASE_URL=postgresql+psycopg://iopsych_readiness:synthetic-local-only@127.0.0.1:5573/iopsych_readiness`;
   target `apps/api/tests/test_database_readiness.py` node IDs
   `test_postgres_statement_and_pool_deadlines`, `test_postgres_lock_deadline`,
   and `test_postgres_actual_migrations_and_search_path`.
   **Exit 0: 3 passed, zero skips, 1 warning, 1.59 s.**
4. Set `IOPSYCH_TEST_LOCAL_MAILPIT=1`; target
   `apps/api/tests/test_local_invitation_delivery.py::test_real_mailpit_capture`.
   **Exit 0: 1 passed, zero skips/warnings, 0.11 s.** Local capture only.

These eleven cases correspond exactly to the broad run's eleven skips: one
assignment-upgrade, three readiness, one Mailpit, three privacy-export, one
report-trace, and two report tests. The broad skip counts remain unchanged;
follow-up execution supplies separate evidence for each case.

## Handoff limits

Next regenerated `apps/web/next-env.d.ts` imports from `.next/dev/types` to
`.next/types`; after inspecting the exact generated delta, it was restored to
HEAD. Lockfiles and app source remain unchanged. No browser, HTTPS staging,
security rescans, hosted CI, deployment, real email, external provider calls,
production secrets, existing database reset, or scientific/product approval was
performed. Integration should apply focused owner corrections and verify the
resulting revision; this checkpoint does not establish release readiness.
