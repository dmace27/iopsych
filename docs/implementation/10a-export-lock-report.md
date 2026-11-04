# 10A assessment export locking slice

Implemented on base `4c7caf3` in the dedicated `iopsych-privacy-lock` worktree.
This completes the decision-independent slice in `10a-contract.md`, not package
10A or any release/pilot gate. Only the allocated privacy service, new
PostgreSQL test file, and this report change.

## Behavior and transaction boundary

Export now acquires `FOR UPDATE OF assessments` through the same tenant-scoped
lookup used by anonymization. Locked lookups refresh existing ORM state, so an
assessment loaded before another transaction erased it cannot bypass the 410
check. The complete schema 1.0 response is constructed and deep-copied while the
transaction still owns the lock. Export does not commit; the existing audited
request middleware commits the response's required audit and releases the lock.
Direct service callers must finish their transaction themselves.

If export wins the assessment lock, anonymization waits until the envelope is
materialized and the transaction finishes. If anonymization wins and commits,
the waiting export sees the tombstone and returns the existing
`candidate_data_anonymized` 410. Tenant filtering and missing/foreign 404
behavior, attachment/no-store headers, schema, retention configuration and
deadlines remain unchanged. No route, migration, dependency, policy or
assignment snapshot changes.

The guarantee is serialization against existing assessment anonymization, not a
global point-in-time snapshot of all unrelated organization/profile edits or
audit writers. A pre-erasure envelope can still arrive at a client after
deletion has committed, and existing downloaded copies cannot be recalled. There
is no delivery lifecycle, server draft, unopened/declined invitation erasure,
withdrawal policy, backup replay or broader 10A acceptance implied. Those remain
gated by the contract's decisions and subsequent integration.

Assessment-first coordination was sent to the coordinator for the report-trace
worker in `msg_f4c17e2c25ee`: preserve the existing assessment lock before
report reads/writes; this slice introduces no invite lock or new lock ordering.

## Actual verification

An exclusively created container `iopsych-privacy-lock-postgres` ran PostgreSQL
**16.15**, bound only to `127.0.0.1:5568`, with disposable synthetic database
`iopsych_privacy_lock` and test-only role `privacy_lock`. Each test created a
random `privacy_export_<uuid>` schema, migrated it through `20261104_0008`,
seeded synthetic rows, and dropped only its own schema. The fixture requires
explicit `TEST_POSTGRES_URL` and never inherits an ambient `DATABASE_URL`. No
existing database was reset; ports 3000/8000/8001 and allocated web/API
3128/8128 were unused. The owned container was stopped after verification.

From `apps/api`:

```sh
TEST_POSTGRES_URL=postgresql+psycopg://privacy_lock@127.0.0.1:5568/iopsych_privacy_lock ../../.venv/bin/pytest tests/test_privacy_export_postgres.py tests/test_privacy.py -q --no-cov
../../.venv/bin/ruff check app/privacy/service.py tests/test_privacy_export_postgres.py
../../.venv/bin/ruff format --check app/privacy/service.py tests/test_privacy_export_postgres.py
MYPYPATH=../../packages/shared/python ../../.venv/bin/mypy app/privacy/service.py tests/test_privacy_export_postgres.py
```

- Pytest: **7 passed, zero skipped, 1 warning, 1.37 seconds**. Three new tests
  ran against actual PostgreSQL; four existing privacy tests used their normal
  SQLite fixture. Coverage enforcement was explicitly disabled for this targeted
  run; this is not a full-suite or 100% coverage claim.
- Export-first test starts deletion after the assessment lookup but before
  report and activity reads, observes its backend blocked via
  `pg_blocking_pids`, checks the full retained envelope, appends an export audit
  and commits, then verifies deletion completes and the detached envelope
  remains unchanged.
- Erasure-first test stages real anonymization without committing, starts export
  on a second connection with preloaded old assessment state, observes
  PostgreSQL blocking, commits deletion, and verifies the waiting export
  returns 410.
- PostgreSQL API test verifies successful audited export, schema 1.0, attachment
  and no-store headers, indistinguishable foreign/missing 404 details, and 410
  after erasure. Existing privacy tests additionally retain permissions,
  retention, scheduler and submission-deadline coverage.
- Ruff lint and format checks passed; Mypy passed for both owned Python files
  with the repository shared-contract source path configured.
- The warning is Starlette's existing httpx TestClient deprecation; no
  dependency change was made. The first test run had six passes and one
  incorrect new assertion (`success` instead of the actual audit value
  `succeeded`); corrected before the passing run. An initial Mypy invocation
  omitted the shared source path and identified two test annotations, all
  resolved in the final invocation.

Report formatting and `git diff --check` were verified before the owned-file
commit. No push, deployment, provider call, real email or purchase occurred.
