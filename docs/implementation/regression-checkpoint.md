# Combined regression checkpoint

Date: 2026-11-04, approximately 22:36–22:40 UTC. Tested application revision:
**`4c7caf31254c4027b917f1afb89cfe08dd428e0e`**, frozen throughout execution.
Dedicated worktree: `iopsych-regression-check`. Task `task_01ab2c204f18`,
dispatch `ctx_38a566c6a71b`.

**Checkpoint executed; combined acceptance fails.** One required PostgreSQL
upgrade case errors before migration because its safety guard hardcodes another
worker's allocation. No application, test, dependency or migration edits were
made. This report is the only committed change. Later integration revisions need
incremental verification; these results do not certify a later HEAD.

## Environment and isolation

- Node `v24.21.0`, npm `11.19.0`, Python `3.12.16`, pytest `9.1.1`.
- Initial working tree was clean. Saved setup completed successfully here.
- Root lock SHA-256: `3955c758b434f3989811f004daef3fc2826e865bd2fcd368fa26621c23310189`.
- Browser lock SHA-256: `c32a4d9a9ad60fdce78c598abb8b87db17ee5a287c96984781a2e5de9824d01f`.
  Both hashes remained unchanged after checks/build.
- Docker context `desktop-linux`, local Unix socket. Fresh container
  `iopsych-regression-4c7caf3` used tmpfs PostgreSQL data, numeric loopback
  `5571:5432`, database/user `iopsych_regression`, synthetic local-only password.
  Image `postgres:16-alpine`, digest
  `sha256:721873c34ceb9f8d8fc265984940dc982404c105f19ad51be9fdc5970a6080ea`.
- Preflight found no competing pytest/check/setup process or listeners on
  8101, 8113 or 5571. The committed launcher test actually uses 8113; coordinator
  confirmed the 6A service/test was stopped and that allocation released.
- Coordinator message `msg_612aff093a9b` reassigned released 1139/8139 for the
  hardcoded SMTP test. After checking both ports free, a new container
  `iopsych-regression-mail-4c7caf3` used `axllent/mailpit:v1.27.10`, loopback-only
  mappings 1139:1025 and 8139:8025, no forwarding/relay configuration or volume.
  No other worker's mail service was used.
- PostgreSQL tests owned UUID schemas. After tests, only `public` remained among
  non-system schemas. Both newly created containers were removed after execution.
  Existing databases and ports 3000/8000/8001 were untouched; 3131/8131 unused.

## Exact commands and results

Commands ran from the worktree root. Raw local logs are retained at
`/tmp/iopsych-regression-4c7caf3/{setup,check,build,schema,mailpit}.log`;
this committed report is the durable evidence summary.

| Command | Result |
| --- | --- |
| `npm ci && PYTHON_BIN=python3.12 npm run api:install` | Exit 0; 471 packages added, 475 audited, zero npm vulnerabilities; Python editable contracts installed successfully. |
| `TEST_POSTGRES_URL='postgresql+psycopg://iopsych_regression:synthetic-local-only@127.0.0.1:5571/iopsych_regression' npm run check` | Exit 1; exactly one broad run, no gate overrides. All format/lint/type stages passed; API setup error below causes aggregate failure. |
| `npm run build` | Exit 0; shared TypeScript and Next.js 16.4.1 webpack production build passed, all 14 listed application routes generated. No build warning. |
| `npm run schemas --workspace @iopsych/shared && git diff --exit-code -- packages/shared/schemas packages/shared/definitions` | Exit 0; existing schema/definition regeneration parity, no drift. |
| `IOPSYCH_TEST_LOCAL_MAILPIT=1 .venv/bin/python -m pytest apps/api/tests/test_local_invitation_delivery.py::test_real_mailpit_capture --no-cov -ra` | Exit 0; 1 passed, zero skipped, zero warnings, 0.12 seconds. Narrow follow-up to the broad run's optional SMTP skip after the coordinator reassigned ports; no aggregate coverage claim for this command. |

Broad check details:

| Stage | Evidence |
| --- | --- |
| Format | Prettier passed; Ruff reported 91 files already formatted. |
| Lint | Web/shared ESLint with zero-warning gate passed; Ruff passed. |
| Types | Next route generation and web/shared TypeScript passed; mypy passed all 80 source files. |
| Web tests | 25 files, 174 tests passed; zero failures/skips. Coverage: statements 92.24% (880/954), branches 87.2% (627/719), functions 91.92% (239/260), lines 93.58% (831/888). |
| Shared TypeScript | 3 files, 99 tests passed; zero failures/skips. |
| Python contracts | 93 passed, zero skipped, 0.32 seconds; required coverage 100.00% reached. |
| API | 321 collected; 319 passed, 1 skipped, 1 warning, 1 setup error, 14.17 seconds; required coverage 100.00% reached, 2374 statements, zero missing. Coverage success does not waive the error. |
| PostgreSQL report tests | Both cases in `test_reports_postgres.py` passed on fresh 5571 database, zero skips; includes real concurrent submission/report behavior and migration to head `20261104_0008`. |
| Populated assignment upgrade | SQLite parameter passed; PostgreSQL parameter errored at fixture guard, before any connection/migration. Required PostgreSQL populated-upgrade evidence remains absent. |

## Failure, skip, warnings and ownership

1. **Blocking — 6C fixture owner/coordinator:**
   `test_assignment_upgrade.py::test_populated_upgrade_preserves_assignments_and_original_interpretation[postgresql]`
   failed during setup at line 46 with
   `Failed: 6C upgrade tests require port 5550 / database iopsych_6c`.
   The fixture explicitly rejects the authorized 5571/iopsych_regression URL.
   Preserve its fail-closed isolation boundary while allowing the explicitly
   allocated fresh database, then rerun the affected PostgreSQL upgrade case
   and fixture validation at the new revision. Do not redirect this checkpoint
   into another worker's database or claim the required zero-error PG gate met.
   Reported immediately in `msg_dd3fd1dedb79`, with observed results in
   `msg_705db3c7a913`.
2. **Resolved narrowly — local delivery test:** broad check skipped
   `test_real_mailpit_capture` because `IOPSYCH_TEST_LOCAL_MAILPIT` was unset
   when the run started; reason `opt-in local sink`. The separate authorized
   real SMTP follow-up passed. The original broad total remains one skip;
   it is not rewritten as an all-green zero-skip run.
3. **Dependency owner:** setup warns `eslint@9.39.5` is no longer supported.
   npm also warns three install scripts lack allowScripts coverage:
   `esbuild@0.28.2`, `fsevents@2.3.3`, `unrs-resolver@1.12.2`.
   No dependency or allowlist changes were made. pip printed only its update
   notice, from 26.2.2 to 26.3; this is informational.
4. **Python dependency/test infrastructure owner:** one API
   `StarletteDeprecationWarning` from `fastapi/testclient.py:1` says httpx use
   with `starlette.testclient` is deprecated in favor of httpx2. This did not
   fail a test. No test/backend dependency changes were made.
5. **Build-generated artifact:** Next changed tracked `apps/web/next-env.d.ts`
   imports from `.next/dev/types` to `.next/types`; only that generated delta
   was restored to the frozen revision after inspecting it. No app patch is
   included in this report commit.

No browser execution (12A owns it), security rescans, staging, deployment,
real email, production secrets, scientific sign-off or existing database reset
was performed. The accelerated schedule remains a throughput target; required
PostgreSQL upgrade acceptance and later integration checks remain open.
