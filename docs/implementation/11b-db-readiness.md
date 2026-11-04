# 11B database budgets and schema readiness

Worker branch: `AbhiNutakki/iopsych-db-readiness`; base `8caf297`. Task:
`task_29879cf69fea`; dispatch: `ctx_e8c966f977cf`. Coordinator approved the
proposed contract through `orca orchestration ask` before implementation. No
migration, dependency, app bootstrap, auth, extraction, or logging changes were
made.

## Implemented contract

The existing database URL, pool size (5), and maximum overflow (10, previously
SQLAlchemy's implicit default) remain compatible. New environment settings:

| Variable                           | Default | Allowed range                            |
| ---------------------------------- | ------- | ---------------------------------------- |
| `DATABASE_CONNECT_TIMEOUT_SECONDS` | 5       | Integer 2–60                             |
| `DATABASE_POOL_TIMEOUT_SECONDS`    | 5       | Finite number greater than 0, at most 60 |
| `DATABASE_MAX_OVERFLOW`            | 10      | Integer 0–50                             |
| `DATABASE_STATEMENT_TIMEOUT_MS`    | 15000   | Integer 1–300000                         |
| `DATABASE_LOCK_TIMEOUT_MS`         | 3000    | Integer 1–60000                          |

These engine knobs apply only to `postgresql+psycopg`. SQLite, including the
in-memory shared-connection fixtures, retains its previous behavior. Settings
are validated; zero/unlimited budgets, negative overflow and nonfinite pool
waits are rejected.

A single URL `options` value is preserved, including a caller's unique
`search_path`. Configured statement and lock limits are appended last and are
**authoritative**, even when earlier startup options specify other timeout
values. Other URL query settings remain intact. Explicit URL `connect_timeout`
and repeated `options` query values fail with a generic configuration error;
move connection timeout configuration to the setting above. An unmatched
trailing backslash in startup options is also rejected so it cannot escape the
appended option boundary. Errors do not contain URL values, credentials, or
configuration details. No diagnostic logging was added.

`/ready` now compares the database's `alembic_version` set with the actual heads
loaded from the packaged Alembic migration directory. There is no hardcoded
revision or environment override, and no migration or stamping occurs during a
probe. Missing, empty, or broken migration assets; absent version table; empty,
stale, or extra database revisions; query failure; and pool exhaustion return
exactly `{"status":"unavailable","service":"api"}` with HTTP 503. Matching heads
return the existing ready body and HTTP 200. Existing no-store behavior and
independent `/health` behavior remain intact. No provider calls occur.
Metadata-only SQLite readiness success fixtures explicitly create the expected
version records; production readiness has no SQLite bypass.

The API Dockerfile already copies `apps/api/alembic`, `alembic.ini`, shared
Python code, and shared definitions. This worker inspected that packaging but
did not rebuild an image or claim hosted acceptance.

## Evidence and exact checks

Installed source inspection used `.venv/bin/python`, `inspect.getsource`, and
`inspect.getdoc` against SQLAlchemy **2.0.54**, psycopg **3.3.6**, and Alembic.
`QueuePool.__init__` documents size 5, overflow 10, and default wait 30 seconds;
`_PGDialect_common_psycopg.create_connect_args` passes URL options to the
driver; `psycopg.Connection.connect` applies the connection timeout per
attempted host; `psycopg.conninfo.timeout_from_conninfo` enforces the two-second
floor; `ScriptDirectory.get_heads` derives revisions from shipped scripts. The
PostgreSQL
[connection parameter documentation](https://www.postgresql.org/docs/current/libpq-connect.html)
corroborates connection-option and per-host timeout behavior.

A new synthetic PostgreSQL 16 container, `iopsych-readiness-ctxe8c966`, was
started with
`docker run --detach --name iopsych-readiness-ctxe8c966 --publish 127.0.0.1:5573:5432 --env POSTGRES_DB=iopsych_readiness --env POSTGRES_USER=iopsych --env POSTGRES_PASSWORD=synthetic-readiness postgres:16-alpine`.
The password is an isolated disposable fixture, not a service credential.
Integration tests refuse another host, port, or database. Only a schema created
by this test was dropped; no existing database was reset. Ports 3000, 8000, and
8001 were untouched.

Executed from the worker root:

```sh
READINESS_TEST_DATABASE_URL='postgresql+psycopg://iopsych:synthetic-readiness@127.0.0.1:5573/iopsych_readiness' .venv/bin/pytest -c apps/api/pyproject.toml apps/api/tests/test_database_readiness.py apps/api/tests/test_runtime_bounds.py apps/api/tests/test_database.py apps/api/tests/test_health.py --no-cov
```

Result: **54 passed, zero skipped, 5.68 seconds**. One existing Starlette/httpx
TestClient deprecation warning. No full suite or global coverage claim. Real
PostgreSQL tests verify `SHOW search_path`, authoritative statement/lock budgets
despite earlier zero settings, `pg_sleep` cancellation (SQLSTATE 57014),
advisory-lock cancellation (55P03), bounded exhausted-pool wait and readiness
503, and actual migrations from missing schema through revision 0007 to the
packaged head. The test-created schema is removed in cleanup.

The stalled local handshake check was then confined to the allocated API port
8133 and rerun individually:

```sh
.venv/bin/pytest -c apps/api/pyproject.toml apps/api/tests/test_database_readiness.py::test_connect_deadline_on_stalled_local_handshake --no-cov
```

Result: **1 passed**. It checks a configured two-second timeout against a local
listener accepting TCP but never completing the PostgreSQL handshake.

```sh
.venv/bin/ruff check apps/api/app/database/config.py apps/api/app/database/session.py apps/api/app/runtime/health.py apps/api/tests/test_database_readiness.py apps/api/tests/test_runtime_bounds.py
.venv/bin/ruff format --check apps/api/app/database/config.py apps/api/app/database/session.py apps/api/app/runtime/health.py apps/api/tests/test_database_readiness.py apps/api/tests/test_runtime_bounds.py
MYPYPATH=packages/shared/python .venv/bin/mypy --config-file apps/api/pyproject.toml apps/api/app/database/config.py apps/api/app/database/session.py apps/api/app/runtime/health.py apps/api/tests/test_database_readiness.py apps/api/tests/test_runtime_bounds.py
```

Results: lint and formatting pass; mypy reports no issues in five source files.
The initial mypy command omitted `MYPYPATH` and reported shared-contract import
resolution errors; the corrected invocation above passes without code changes.
Initial lint formatting findings were fixed before the passing checks.

## Remaining boundaries

Connection timeout is per host, not a global multi-host hard deadline. DNS,
network blackholes after connection, pool pre-ping/reconnect, and aggregate
request work can exceed an individual configured budget. Server-side statement
and lock timeouts do not provide client-side cancellation for a broken network.
Migration commands still use their existing separate engine configuration.
Schema readiness verifies migration metadata, not arbitrary manual schema drift
or restored-data correctness. Injected custom session factories remain
responsible for their own engine budgets.

Full hosted configuration, actual staging/provider smoke, deployment packaging
revalidation, rollback/restore rehearsal, and combined integration regression
remain coordinator-owned gates. This scoped implementation does not declare
package 11B or hosted readiness accepted. No push, deployment, purchase, real
email, external provider request, or Fast-mode toggle was performed.
