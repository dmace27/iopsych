# Telemetry and migration logging interaction

Validated November 4, 2026 on child-worktree baseline `60cacf6`.

## Root cause and change

Alembic's `env.py` called `logging.config.fileConfig` with its default
`disable_existing_loggers=True`. Migration tests therefore disabled the already
imported `app.runtime.telemetry` logger. Middleware initialization sets INFO but
does not clear `Logger.disabled`; subsequent requests emitted no captured record.
This explains why telemetry passed alone but failed after migrations. The four
parameterized incoming-ID cases explicitly use `caplog.set_level`, which also
reenables their logger temporarily; other capture assertions did not.

With coordinator authorization for `alembic/env.py`, the fix explicitly passes
`disable_existing_loggers=False`. Existing application logging remains enabled
when migrations run in-process. No runtime telemetry, main, security, migration
revision, schema, dependency, or privacy-redaction behavior changed.

The new regression runs actual migrations against an in-memory SQLite database,
asserts the logger remains enabled, then checks an emitted completion record with
the existing strict privacy/shape assertions. It saves logger configuration for
test teardown and reattaches pytest's capture handler after Alembic deliberately
replaces root handlers; it never repairs logger disabled state before assertions.
Additional checks cover the standalone fallback handler without duplicate output,
and an interrupted response whose oversized route must stay unmatched.

## Evidence

Minimal pre-fix reproduction, from `apps/api`:

```sh
../../.venv/bin/pytest tests/test_database_migrations.py::test_documented_seed_and_verify_commands tests/test_telemetry.py::test_500_is_correlated_once_without_exception_text -q --cov=app.runtime.telemetry --cov-fail-under=0
```

Result: one passed, one failed with expected one telemetry record, got zero.
Coverage was collected for diagnosis; this was not a coverage acceptance run.
Temporarily restoring the original `fileConfig` call also made the new regression
fail specifically at `assert not logging.getLogger(LOGGER).disabled`; the fixed
call was restored before final validation.

Final targeted sequence, from `apps/api`:

```sh
../../.venv/bin/pytest tests/test_database_migrations.py tests/test_telemetry.py tests/test_runtime_bounds.py tests/test_security.py -q -o 'addopts=--strict-config --strict-markers --cov=app.runtime.telemetry --cov-report=term-missing --cov-fail-under=100'
MYPYPATH=../../packages/shared/python ../../.venv/bin/mypy tests/test_telemetry.py
../../.venv/bin/ruff check tests/test_telemetry.py alembic/env.py
../../.venv/bin/ruff format --check tests/test_telemetry.py alembic/env.py
```

Results: **60 passed**, telemetry **100% statement and branch coverage**, type
check and lint/format passed. One existing FastAPI/Starlette TestClient deprecation
warning remains. The initial type-check invocation without the local contracts
path could not resolve shared modules; the documented invocation passes.

## Remaining integration

No full-suite run was duplicated here. The coordinator/regression owner should
integrate this commit and perform one combined follow-up with the other fixes;
this targeted coverage result is not a claim of global API coverage. No ambient
database, network listener, external provider, real email, secret, push, or deploy
was used. There are no migrations or contract changes to allocate.
