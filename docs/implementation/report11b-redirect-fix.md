# 11B credential redirect boundary fix

Date: 2026-11-04. Branch: `AbhiNutakki/iopsych-redirect-fix`. The commit containing
this report is the tested implementation revision. Scope is the assigned
credential redirect defect, not full 11B or release acceptance.

Read the final implementation plan, progress ledger, extraction bounds report,
and independent review at `runtime-version-review.md` (review commit `e84cb96`).
No applicable root/API AGENTS file exists; the web-only instructions do not apply.
Requested the reviewer's probe through Orca and received its location through
the coordinator.

## Fix and regression

The default extraction transport now builds a local stdlib opener with automatic
redirect handling disabled for 301, 302, 303, 307 and 308. It never constructs or
sends a redirected request, including same-origin redirects. Other non-success
3xx statuses retain urllib's default HTTP error handling. The existing HTTP error
path closes the response and raises a generic, non-retryable provider error with
the raw exception suppressed. No redirect response body is read by the handler.
No global opener is installed. The existing `provider.urlopen` injectable hook,
request schema, byte limits, timeout and elapsed-budget behavior remain intact.

The new 15-case matrix uses the actual provider and stdlib opener. Only
`HTTPHandler.http_open` and `HTTPSHandler.https_open` are replaced with in-memory
responses, preventing network access while retaining the real response/error/
redirect chain. It covers all five statuses against same-origin HTTPS,
cross-origin HTTPS and cross-origin HTTP downgrade destinations. Each case
checks exactly one initial credential-bearing request, no follow-up, response
closure, terminal failure, no service retry with three attempts configured, no
profile persistence, and no synthetic secret in formatted tracebacks or captured
exception logs. Synthetic secrets also appear in Location, response reason and
body to exercise error redaction.

Before the implementation change, the matrix produced **9 failures and 6 passes**:
301/302/303 each made five requests before urllib's redirect-loop rejection;
307/308 already rejected the POST. After the fix, all 15 cases pass. The original
review probe substitutes an unrestricted opener for `provider.urlopen`; doing
that after this fix would explicitly replace the protected transport. Independent
rechecks should instead patch the socket-facing handlers as the regression does.

## Exact checks

From `apps/api`:

```sh
../../.venv/bin/pytest tests/test_extraction_bounds.py -k stdlib_redirects --no-cov -q
../../.venv/bin/pytest tests/test_role_extraction.py tests/test_extraction_bounds.py --no-cov -q
MYPYPATH=../../packages/shared/python ../../.venv/bin/mypy app/extraction/provider.py --follow-imports=silent
```

The first command is the pre-fix red run described above. The second is the
post-fix run: **80 passed in 0.91 seconds**, no skips. Mypy passed for the provider.
Whole-application coverage is intentionally disabled for this targeted run.

From the repository root:

```sh
.venv/bin/ruff check apps/api/app/extraction/provider.py apps/api/tests/test_extraction_bounds.py
.venv/bin/ruff format --check apps/api/app/extraction/provider.py apps/api/tests/test_extraction_bounds.py
git diff --check
```

All passed. The first format check requested a one-line signature; applied Ruff
format and reran successfully. No behavior changed during formatting.

## Remaining scope

Coordinator integration and independent recheck remain. Existing hard wall-clock
cancellation, distributed admission, hosted/provider smoke and other package
acceptance gates remain unchanged. Only the provider, its focused tests and this
report changed. No dependencies, configuration, service code, external/paid
requests, real secrets, database changes, listeners, pushes or deployments were
used. Reserved ports 3140/8140/5580 were unused.
