# 10C bounded retention drain

This completes only the independently assigned bounded CLI drain slice. It does
not complete package 10C or authorize real candidate use.

## Contract and compatibility

The existing command continues to process exactly one configured service batch
and retains its existing count-only human-readable success output. No retention
settings, service policies, API contracts, models, or migrations change.

Explicit opt-in example, only after verifying an isolated synthetic database
target:

```sh
npm run privacy:retention -- --drain --max-batches 20 --max-seconds 60
```

Both bounds are required with `--drain`; either bound without `--drain` is
rejected. Batch count must be a positive integer and seconds must be finite and
positive. Invalid arguments exit 2 before database initialization and do not
echo input. The existing configured batch size still limits each service
invocation.

Drain success emits one JSON object on stdout with these allowlisted fields:

```json
{
  "assessments_anonymized": 12,
  "attempted_batches": 3,
  "completed_batches": 3,
  "stop_reason": "max_batches"
}
```

Stop reasons are `max_batches`, `time_budget`, `no_progress`, and `error`. The
monotonic elapsed budget includes initialization and is checked immediately
before each batch attempt. It prevents starting additional batches; it does not
cancel a transaction already in flight or impose a database statement timeout.
Each invocation uses a fresh session and the existing service-owned commit. Zero
progress stops immediately; a short nonzero batch may be followed by another
attempt within both bounds. Simultaneous stop conditions prefer `no_progress`,
then `max_batches`, with time checked before the next batch.

No candidate IDs, email addresses, credentials, payloads, or raw exceptions
enter the CLI summary. Exceptions during initialization, service execution,
session cleanup, or engine disposal produce a safe error summary and exit 1. The
counts record service calls that returned successfully; a failed commit
acknowledgment can leave database outcome uncertain and requires reconciliation.
There is no automatic retry of a failed batch. Existing external logging
configuration is outside the summary contract.

Neither zero progress nor any other stop reason claims the backlog is empty:
PostgreSQL `SKIP LOCKED` can hide rows held by other workers. A subsequent run
or authorized status reconciliation may still find due records. Existing default
success wording refers only to completion of one invocation.

## Validation

Executed from repository root:

```sh
.venv/bin/python -m pytest -c apps/api/pyproject.toml apps/api/tests/test_retention_drain.py apps/api/tests/test_privacy.py --override-ini='addopts=--strict-config --strict-markers' --cov=app.privacy.retention --cov-branch --cov-report=term-missing --cov-fail-under=100 -q
.venv/bin/python -m ruff format --check apps/api/app/privacy/retention.py apps/api/tests/test_retention_drain.py
.venv/bin/python -m ruff check apps/api/app/privacy/retention.py apps/api/tests/test_retention_drain.py
MYPYPATH=packages/shared/python .venv/bin/python -m mypy --config-file apps/api/pyproject.toml apps/api/app/privacy/retention.py apps/api/tests/test_retention_drain.py
```

Results: 27 tests passed, zero skips; formatting, lint, and strict typing
passed. This targeted run intentionally disables the repository-wide coverage
threshold; it is not a full-suite coverage claim. Initial test fixture failures
(missing required synthetic model fields and mock-factory depth) and typing/lint
failures were corrected before this final passing run.

Mocked tests cover default compatibility, max batch bound, short-batch progress,
zero progress, time expiry before the first/next batch, invalid bounds
(including NaN/infinity), partial failure without sensitive exception output,
initialization failure, disposal failure, and executable module help parsing.
Integration uses only the explicit in-memory SQLite fixture from
`tests/conftest.py`, seeds both synthetic tenants, and adds four due submitted
records, one future submitted record, and one unsubmitted record. Runs process
three then one then zero records; exactly four anonymization audit events
persist and both controls retain their responses. No ambient/default database
command was executed. No PostgreSQL, network listener, mail, or protected port
was used.

## Partial acceptance and handoff

Files: `apps/api/app/privacy/retention.py`, new
`apps/api/tests/test_retention_drain.py`, and this report. No inline comments
were added. No schema migration, configuration migration, scheduled
installation, retention period/category, notice, or backup change is needed for
this slice.

Remaining package gates: approved lifecycle coverage/policy, unattended
scheduler and overlap policy, overdue/missed-run measurement and alert receipt,
PostgreSQL concurrency rehearsal, and actual backup-restore deletion replay. The
historical `docs/operations/retention-recovery.md` description of no automatic
drain is superseded only for this opt-in CLI capability; its scheduling/recovery
gates remain valid. Next eligible work is coordinator review/integration and
targeted combined regression, followed by scheduler/monitoring/recovery work
when its policy and deployment dependencies are satisfied.
