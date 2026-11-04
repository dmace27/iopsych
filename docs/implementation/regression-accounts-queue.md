# Frozen account and delivery queue regression

Checkpoint: `444dcb0`, with only the defensive tests in this receipt added. Read
`final-implementation-plan.md` and `docs/implementation/progress.md` before
execution. This is bounded regression evidence, not full package acceptance.
Incoming delivery visibility API/UI and privacy related-audit changes, and
post-freeze historical-fixture repairs, are outside this checkpoint.

## Change

Added two PostgreSQL cases to `test_delivery_queue.py` for cleanup's final
defensive recheck: the selected delivery disappears, or it becomes terminal. The
tests inject the change at `_locked_job` after real database selection and
assert zero cleanup count, no added audit, no invitation activation, and no
credential/attempt resurrection. This is deliberate fault injection, not a claim
that ordinary invite-lock serialization permits this race. No application,
dependency, migration, or coverage-policy changes were made.

## Isolation and reproducible commands

Every test process used an allowlisted environment containing only inherited
`PATH`, `HOME`, optional `TMPDIR`, and the following explicit opt-ins:

```text
TEST_DELIVERY_POSTGRES_URL=postgresql+psycopg://synthetic:synthetic-local-only@127.0.0.1:5586/iopsych_delivery
ACCOUNT_TEST_POSTGRES_URL=postgresql+psycopg://synthetic:synthetic-local-only@127.0.0.1:5594/iopsych_access
TEST_POSTGRES_URL=postgresql+psycopg://synthetic:synthetic-local-only@127.0.0.1:5571/iopsych_regression
READINESS_TEST_DATABASE_URL=postgresql+psycopg://synthetic:synthetic-local-only@127.0.0.1:5573/iopsych_readiness
IOPSYCH_TEST_LOCAL_MAILPIT=1
```

Root and API `.env` files were absent. Ambient database URLs, PostgreSQL service
or host overrides, proxy settings, and `PYTEST_ADDOPTS` were not inherited. Four
newly created `postgres:16-bookworm` containers had tmpfs data directories,
loopback-only allocated ports, and the synthetic credentials above. A fresh
`axllent/mailpit:v1.27.10` container used tmpfs `/data` and loopback ports
1139/8139, without relay configuration. All five were named
`accounts-queue-809b-*` and labeled `orca.dispatch=ctx_809b0471d83c`. Existing
containers and databases were neither used nor reset. Launcher 8113 and
readiness/stall 8133 remained within this worker's allocation.

The canonical commands were:

```sh
npm run check
npm run build
npm run schemas --workspace @iopsych/shared
git diff --exit-code -- packages/shared/schemas
```

## Results and failures

| Check                         | Result                                                            |
| ----------------------------- | ----------------------------------------------------------------- |
| Formatting, lint, type checks | Passed; mypy 114 source files                                     |
| Web                           | 446 passed in 40 files; configured coverage gates passed          |
| Shared TypeScript             | 99 passed in 3 files                                              |
| Python contracts              | 93 passed, 100% required coverage                                 |
| API canonical                 | 934 passed, 2 failed, zero skips; 1 Starlette deprecation warning |
| API canonical coverage        | Failed required 100% gate: 99.83%, 3441 statements, 6 missing     |
| Worker canonical coverage     | 126 statements, zero missing, 100%                                |
| Production build              | Passed                                                            |
| Regenerated schema parity     | Passed; no tracked schema difference                              |

Web tests were repeated in the canonical check, despite permission to reuse the
prior run: `444dcb0:apps/web` and `e439208:apps/web` both resolve to
`42129c6c3100c75217d70a4e2eb2924e9c976ff2`. All opt-in PostgreSQL and Mailpit
tests actually executed, including queue transactions, account concurrency and
populated 0010 rollback guard, readiness deadlines/migrations, report/privacy
serialization, and local mail capture. The historical upgrade tests executed but
failed; they are not accepted.

Both failures are
`test_assignment_upgrade.py::test_populated_upgrade_preserves_assignments_and_original_interpretation`
(`sqlite` and `postgresql`): line 97 calls the current `seed_database` against
schema 0007, which lacks `users.is_active`. SQLite raises `OperationalError`;
PostgreSQL raises `UndefinedColumn` wrapped as `ProgrammingError`. Uncovered
canonical lines are `accounts/service.py:30,32,60,104` and
`invitations/service.py:120,230`. Exact results were sent to the coordinator in
`msg_ffce2d567c79`; these application/fixture repairs are outside this
ownership. The frozen check remains failed regardless of newer integrated
repairs.

The check wrapper began a redundant lint fallback, which also passed; it was
stopped before repeating type checks or the full test command. The canonical
`npm run check` itself completed with exit 1. Build and parity ran independently
after the test failure. Next generated two route-type import changes in
`apps/web/next-env.d.ts`; those generated changes were inspected and restored.

## Limits

The canonical coverage output did not include branches, so the full API suite
was additionally run with the same isolated environment and the committed branch
configuration explicitly selected:

```sh
.venv/bin/python -m pytest apps/api --cov-config=apps/api/pyproject.toml
```

This also completed with 934 passes, the same two failures, zero skips, and one
warning. **The worker reached 100%: 126 statements, 28 branches, zero missing
statements or partial branches.** Overall coverage still failed at 99.66% (3441
statements, 6 missing; 684 branches, 8 partial). In addition to the canonical
missing lines, uncovered branches include `auth/dependencies.py:27->32` and
`privacy/service.py:295->292`. No reduced threshold, coverage exclusion, or
narrower measured source scope was used for this follow-up.

All five owned containers were stopped after verification. Raw logs are local
ephemeral files `/tmp/accounts-queue-809b-{check,build,schemas,branches}.log`;
this receipt preserves the results without depending on those files.

No browser or shared runtime suite, staging, deployment, real mail, external
provider, production secret, existing database reset, or approval of scientific,
product, privacy, or operational decisions is included. No threshold was lowered
and no missing lines were excluded. The coordinator remains sole integrator.
