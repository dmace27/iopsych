# 11B extraction resource bounds — scoped implementation

Date: 2026-11-04. Branch: `AbhiNutakki/iopsych-extraction-bounds`. Baseline:
`c20b3ed`. The implementation and this report are committed together; use the
commit containing this report as the tested revision.

This completes the assigned extraction-only slice, not package 11B or release
acceptance. Reviewed the final implementation plan, MVP specification, finish
findings, and coordination ledger. No applicable API/root AGENTS file was found;
the web-only AGENTS file does not apply to this work.

## Changes and configuration

All settings use the existing `ROLE_EXTRACTION_` environment prefix. Each new
numeric field has validated lower and upper bounds.

| Setting suffix            |   Default |               Allowed range |
| ------------------------- | --------: | --------------------------: |
| `TOTAL_BUDGET_SECONDS`    |        45 | greater than 0, at most 120 |
| `MAX_RESPONSE_BYTES`      | 1,048,576 |                 1–8,388,608 |
| `MAX_OUTPUT_BYTES`        |    65,536 |                 1–1,048,576 |
| `MAX_OUTPUT_TOKENS`       |     8,192 |                   16–32,768 |
| `MAX_CONCURRENT_REQUESTS` |         4 |                        1–32 |

The urllib response read now requests at most `MAX_RESPONSE_BYTES + 1` bytes,
rejecting oversize before decoding JSON. Structured text has an independent
UTF-8 byte cap before JSON parsing. Size breaches are terminal, so retries do
not amplify them. Malformed Unicode, excessive JSON nesting, socket errors, and
HTTP protocol failures become safe provider errors. HTTP error response handles
are closed without reading their bodies. Ordinary exception tracebacks suppress
raw transport errors and validation details; no payload logging was added.
Telemetry that captures exception locals or introspects suppressed contexts
still requires its own redaction policy.

The request sends `max_output_tokens`. No local installed OpenAI SDK or API
reference was found, so the official
[Responses create reference](https://developers.openai.com/api/reference/resources/responses/methods/create)
was fetched on 2026-11-04 before adding the parameter. It documents an integer
minimum of 16 and a limit including visible output and reasoning tokens. No
other API field, model, scientific interpretation, or provider choice changed.
Token limits and attempt counts bound generated-token exposure; they are not a
currency quota and do not guarantee a successful extraction at a given limit.

The service shares one monotonic deadline across attempts, validation, and
backoff. It refuses attempts/backoff that cannot start within the remaining
budget, reduces the adapter's socket timeout to the remaining budget, and
rejects late successful results before creating a draft. The injectable
`extract(role)` protocol and response/error contracts remain unchanged; a
private context variable carries the deadline only during synchronous service
execution and is reset in `finally`.

A lock-protected process-local admission set caps whole service operations,
including retries and persistence, and rejects simultaneous extraction of the
same role. Rejection uses the existing generic `role_extraction_failed` 502
contract, with no transport call and no waiting queue. Capacity and duplicate
admission are released on success or failure. Sequential repeated requests
remain allowed. The existing schema, source-grounding, tenant/lifecycle, audit,
and mandatory human-approval paths remain in place.

## Targeted verification

Run from `apps/api`:

```sh
../../.venv/bin/pytest tests/test_role_extraction.py tests/test_extraction_bounds.py --no-cov -q
MYPYPATH=../../packages/shared/python ../../.venv/bin/mypy app/extraction/config.py app/extraction/provider.py app/extraction/service.py --follow-imports=silent
```

Results: **65 passed in 1.28 seconds**, no skips; mypy passed for all three
production files. The initial mypy invocation omitted `MYPYPATH` and failed to
resolve the existing local `iopsych_contracts` package; the corrected command
above passed without source changes. Whole-application coverage was deliberately
disabled for this targeted run; no full-suite or 100% coverage claim is made.

Run from repository root:

```sh
.venv/bin/ruff check apps/api/app/extraction apps/api/tests/test_extraction_bounds.py apps/api/tests/test_role_extraction.py
.venv/bin/ruff format --check apps/api/app/extraction apps/api/tests/test_extraction_bounds.py apps/api/tests/test_role_extraction.py
git diff --check
```

Ruff lint/format and diff checks passed. Synthetic mocked transport covers
bounded read size and closure, exact byte boundaries, multibyte output,
malformed Unicode/deep JSON, timeout during read, expired/late completion,
shrinking retry timeouts, no retry after oversized output, exhausted/overslept
backoff, simultaneous capacity and duplicate rejection, cleanup, and traceback
redaction. The existing extraction test file only changes its response mock to
accept the standard `read(size)` argument. Existing integration tests continue
to cover semantic rejection, tenant isolation, draft-only creation, manager
approval, and rollback on audit failure. Tests use in-memory SQLite and mock
transport; no provider requests, databases, or listeners were started.

## Remaining limits and next work

- This is an elapsed retry budget, **not hard total wall-clock cancellation**.
  urllib's timeout applies to blocking socket operations. DNS, redirects,
  multiple operations, or a trickling response can outlive the budget; the
  synchronous call cannot be forcibly cancelled here. Late results are rejected
  once control returns. The mocked stall test proves timeout handling, not a
  real-network wall-time guarantee.
- The budget does not cover role lookup or database persistence latency. The
  existing synchronous interface still blocks an async caller if used directly;
  coherent offloading/cancellable transport belongs to the router/runtime owner.
- Admission applies to the service path, not direct calls to the provider
  adapter. Its counter and in-flight duplicate guard are shared within one
  Python process, not across worker processes/replicas. Deployments should use
  one consistent settings object per process. Shared admission/rate limits,
  durable idempotency, per-tenant fairness, and spend quotas remain separate
  work.
- No live provider smoke, hosting validation, ingress bounds, or readiness work
  was performed. The current token/default budget requires synthetic staging
  validation with authorized provider access before deployment acceptance.
- No migrations, dependencies, shared schemas, main/router code, or progress
  ledger edits. No pushes, deployments, real email, purchases, production
  secrets, or database resets. Reserved ports 3119/8119/5559 and database
  `iopsych_extraction` were unused; protected ports were untouched.

Next eligible work is runtime-owner integration review and coherent blocking-I/O
handling, then authorized synthetic staging verification and shared admission
controls. Product, scientific, provider, and release approvals remain unresolved
where previously unresolved.
