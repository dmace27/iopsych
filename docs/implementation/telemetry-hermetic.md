# Hermetic telemetry and migration logging tests

The minimal migration-to-telemetry sequence reproduced the reported failure on
base commit `ba2759a`: 32 tests passed and the candidate-route case returned 404
instead of its expected 503. A synthetic `INVITE_TOKEN_SIGNING_SECRET` was enough
to reproduce it; no integration environment file or existing secret was inspected
or copied. The same run exposed `Logging error` and `I/O operation on closed file`
in captured stderr.

The candidate-route test now injects
`InvitationSettings(_env_file=None, token_signing_secret=None)`, making its
unconfigured-signing expectation explicit even when the process has a signing key.
The migration test module provides an autouse logging-state fixture, explicitly
re-exported by the telemetry module. It restores logger levels, disabled flags,
propagation, handlers, and filters after each test. It also isolates the logging
handler registries so Alembic's real `fileConfig` cannot close the caller's
handlers, closes handlers created inside the test, and clears cached level checks
when restoring configuration. This removes the migration-created root handler
before its capture stream can escape into later tests.

The actual migration-to-request regression still runs Alembic logging
configuration, asserts that telemetry was not disabled, attaches pytest's capture
handler, and asserts the completion record. No production telemetry code,
assertions, warning filters, or expected migration tables changed. The coordinator
approved the migration-file fixture/import boundary; the delivery worker retains
ownership of migration 0009 and expected-table changes.

## Validation

From the child worktree root, the minimal sequence was run in fresh Python child
processes with the signing variable removed and with the synthetic key below:

```sh
env -u INVITE_TOKEN_SIGNING_SECRET .venv/bin/python -m pytest \
  -c apps/api/pyproject.toml --no-cov \
  apps/api/tests/test_database_migrations.py::test_documented_seed_and_verify_commands \
  apps/api/tests/test_telemetry.py -q -rP

INVITE_TOKEN_SIGNING_SECRET=synthetic-telemetry-test-key-000000000000 \
  .venv/bin/python -m pytest -c apps/api/pyproject.toml --no-cov \
  apps/api/tests/test_database_migrations.py::test_documented_seed_and_verify_commands \
  apps/api/tests/test_telemetry.py -q -rP
```

Both configurations passed all 33 tests. A final child-process harness invoked
the same sequence through `pytest.main`, with a pre-existing root `FileHandler`.
After pytest returned, the harness asserted that this handler remained attached
and open, that no root handler referenced a closed stream, and that a new warning
was successfully written to the original file. Both harness runs passed. Complete
passing-test capture output was checked for both logging-error markers, with none
present; local logs are `/tmp/telemetry-hermetic-unconfigured.log` and
`/tmp/telemetry-hermetic-synthetic-key.log`.

The existing Starlette/httpx deprecation warning remains visible in both runs.
All four tests in `test_database_migrations.py` also passed. Ruff lint and format
checks and `git diff --check` passed. Mypy passed for the two changed test files
with `MYPYPATH=packages/shared/python`; the initial invocation without that path
could not resolve the local contracts package.

Only focused tests were run; `--no-cov` bypasses the repository-wide coverage gate
for this targeted validation. The logging fixture deliberately uses Python's
private handler registry names to preserve existing handlers across real
`fileConfig` calls, so future Python logging implementation changes may require
adjusting this test helper. Validation used the existing Python 3.12 environment,
in-memory or temporary SQLite databases, and in-process test clients. Integration
of this child commit and the separately owned delivery changes remains with the
coordinator.
