# Report trace boundary regression tests

Implemented on the isolated `AbhiNutakki/iopsych-trace-coverage` worktree from
baseline `b7ae145`. Scope is the new boundary test module and this report only;
no production, dependency, migration, or coverage configuration changes.

The 14 new cases cover the four requested previously uncovered lines:

- `reports/trace.py:49`: nine API cases persist nonempty arrays, strings, and
  numbers in assessment definition, response, and score JSON. Each receives a
  generic 409 with no trace or corruption content, a no-store header, and a
  metadata-only rejected audit. Stored corruption remains unchanged and the
  historical report remains exactly readable.
- `reports/trace.py:69`: three builder cases reject malformed retained assignment
  snapshots without mutating any input. These use the existing synthetic source
  fixture because the database correctly prevents updates to assigned versions;
  the tests do not disable or bypass that protection.
- `reports/service.py:228`: a persisted invitation points to a different valid
  profile version in the same tenant. Trace fails with 409, while the saved
  report remains exactly readable and neither link nor snapshot is repaired.
- `reports/service.py:219`: an SQLAlchemy execution event deletes real report/item
  rows immediately before the second trace query. The real query returns no row,
  the API returns 404 without evidence, subsequent report reads return 404, and
  the assessment remains intact. The listener is removed in a finally block.

The deletion case is deterministic fault injection in an isolated in-memory
SQLite database, not evidence that this interleaving can bypass PostgreSQL's
assessment lock. No query result, production function, or service return is
mocked. PostgreSQL serialization remains covered by the existing separate test,
which was explicitly deselected for this bounded run. No ambient database or
network listener was used.

## Verification

From `apps/api`:

```sh
../../.venv/bin/pytest tests/test_report_trace_boundaries.py tests/test_report_trace.py tests/test_reports.py tests/test_privacy.py::test_admin_export_and_anonymization_are_tenant_scoped_and_audited -k 'not postgres' -o addopts='' --cov=app.reports --cov-branch --cov-report=term-missing --cov-fail-under=100 -q
../../.venv/bin/mypy tests/test_report_trace_boundaries.py --follow-imports=silent
../../.venv/bin/ruff check tests/test_report_trace_boundaries.py
../../.venv/bin/ruff format --check tests/test_report_trace_boundaries.py
```

Results: **75 passed, 1 deselected**; `app.reports` **100.00%**, with all 254
statements and 66 branches covered and no partial branches. Mypy, Ruff lint, and
format verification passed. The initial focused selection omitted the existing
privacy anonymization regression and consequently left `service.py:71` uncovered;
adding that single existing test produced the complete focused report result.

No full suite or PostgreSQL tests were run. Combined API coverage and integration
with the separate typing/telemetry workers remain the coordinator's work; this
focused result is not a claim about combined API coverage or release acceptance.
No migration or dependency work is needed. The next eligible step is coordinator
integration and the already planned combined validation.
