# Test typing corrections

Corrected the ten frozen-regression mypy errors in the three assigned test files.
Work was performed in the dispatched child worktree on branch
`AbhiNutakki/iopsych-test-typing`; no applicable AGENTS.md was present for these paths.
Only the three test files and this report changed.

## Changes

- Extraction bounds: use a tracking BytesIO subclass instead of assigning its read
  method, and match the `int | None` positional read signature in both response
  doubles. The stalled-read assertion still requires a positive bounded read.
- Redirect handling: declare the synthetic response's `msg` attribute on a small
  addinfourl subclass and type the collected responses. Real urllib redirect
  processing and all closure, redaction, retry, and request-count checks remain.
- Persistence double: return a validated RoleProfileResponse populated from the
  actual role ID, request constructs, and assumptions, with draft status and no
  approval. Successful admission/retry assertions now check that draft status
  instead of comparing the response to an impossible string value.
- Trace helpers: narrow decoded JSON from object to a dictionary and assert
  string keys before returning; nested fixture data remains dynamically typed.
- Upgrade guards: use inspect.unwrap with a narrowly scoped callable cast matching
  the underlying generator fixture, and pass a real pytest FixtureRequest with
  its parameter temporarily patched. Engine rejection and generated-schema
  creation/cleanup assertions are unchanged.

No new ignores, configuration changes, production changes, or removed test cases.
The existing method-assignment ignore was removed.

## Validation

The available environment was `/Users/abhiramnutakki/iopsych/.venv/bin/python`
(pytest 9.1.1). Commands were run from the child worktree root.

Before editing, targeted strict mypy reproduced exactly ten errors: six extraction
bounds errors, two trace Any-return errors, and two fixture-wrapper attribute errors.
After editing, the same command passed for all three files:

```sh
MYPYPATH=apps/api:packages/shared/python /Users/abhiramnutakki/iopsych/.venv/bin/python -m mypy --config-file apps/api/pyproject.toml apps/api/tests/test_extraction_bounds.py apps/api/tests/test_report_trace.py apps/api/tests/test_assignment_upgrade_guards.py
```

The complete configured strict typecheck also passed: **97 source files**.

```sh
MYPYPATH=apps/api:packages/shared/python /Users/abhiramnutakki/iopsych/.venv/bin/python -m mypy --config-file apps/api/pyproject.toml apps/api/app apps/api/tests packages/shared/python/iopsych_contracts packages/shared/python/tests scripts/security_smoke.py
```

Focused runtime checks: **131 passed, 1 skipped**. No full test suite was run.
Coverage measurement was disabled only for this focused invocation; repository
coverage configuration and test coverage assertions were not changed.

```sh
env -u DATABASE_URL -u TEST_POSTGRES_URL PYTHONPATH=apps/api:packages/shared/python /Users/abhiramnutakki/iopsych/.venv/bin/python -m pytest -c apps/api/pyproject.toml apps/api/tests/test_extraction_bounds.py apps/api/tests/test_report_trace.py apps/api/tests/test_assignment_upgrade_guards.py --no-cov -q -p no:cacheprovider
```

Both `ruff check` and `ruff format --check` passed for all three test files;
`git diff --check` passed.

The PostgreSQL trace/deletion concurrency test was skipped because there was no
allocated isolated PostgreSQL instance. Ambient DATABASE_URL and TEST_POSTGRES_URL
were explicitly removed for the test invocation. Upgrade guard URLs were synthetic
inputs to mocked engines only; no ports were opened and no external database,
provider, mail, push, deployment, purchase, or secret access was used.

Coordinator integration remains; PostgreSQL concurrency execution requires a
separately authorized isolated allocation.
