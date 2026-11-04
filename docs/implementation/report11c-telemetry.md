# 11C safe API telemetry slice

Implemented in child worktree `AbhiNutakki/iopsych-safe-telemetry` from
`8caf297e5e26b2a380a5195ed8f58618d5018c83`. This report belongs to the same
scoped commit as the implementation. The coordinator approved the exact proposed
additive contract before middleware wiring. No migration or dependency change.

## Contract and integration

Every HTTP request receives a fresh server-generated UUID4 in `X-Request-ID`.
All incoming request IDs, including syntactically valid UUIDs, are ignored.
Downstream request-ID response headers are replaced. The UUID object is stored
in the ASGI scope; the existing outer unexpected-error handler reuses it for 500
responses without reflecting exception details.

The completion middleware wraps security, request-body limits, and audit
middleware. Thus early 408, 413, and security rejections remain correlated. It
emits one JSON record through `app.runtime.telemetry` at INFO on completion or
unwind. A local stderr handler is installed only when no logging handler already
exists; normal configured logging handlers otherwise receive records. Non-HTTP
scopes pass through unchanged.

The only payload fields are:

| Field          | Allowed value                                                                                    |
| -------------- | ------------------------------------------------------------------------------------------------ |
| `event`        | `request_completed`                                                                              |
| `request_id`   | Server UUID4                                                                                     |
| `method`       | GET, HEAD, POST, PUT, DELETE, CONNECT, OPTIONS, TRACE, PATCH, or OTHER                           |
| `route`        | Registered route template captured at middleware startup, maximum 256 characters, or `unmatched` |
| `status_class` | 1xx through 5xx, or `unknown`                                                                    |
| `duration_ms`  | Monotonic integer duration clamped to 0–86,400,000                                               |
| `release_id`   | `IOPSYCH_RELEASE_ID` matching `[A-Za-z0-9][A-Za-z0-9._-]{0,63}`, otherwise `unknown`             |

Release configuration is read when the middleware stack initializes. Operators
must use a non-sensitive build identifier. Request data never supplies this
value. Route capture uses FastAPI's route-context iterator to include lazy
included routers and configured prefixes; ambiguous duplicate route identities
use `unmatched`. Routes added after startup also fail closed to `unmatched`. No
raw request path is used to construct a label, including unknown paths and
bearer-bearing candidate URLs. Early pre-routing failures use `unmatched`.

JSON uses standard escaped slashes so the existing process-wide candidate-token
redactor does not replace a harmless registered `{token}` template. Parsing the
record yields the original registered template. No incoming headers, query,
body, user, organization, email, IP, token, exception representation, traceback,
or arbitrary structured extras are emitted by this telemetry boundary.

An exception before response start records 5xx and is re-raised to the existing
500 handler; that handler does not log another completion. Cancellation and
incomplete responses use `unknown`, including cancellation after a 200 start. No
success is inferred merely from entering a route. Duration measures the
middleware lifecycle, including body receipt and response delivery, rather than
provider time or financial/provider usage.

## Exact verification

All checks used synthetic in-process requests and mock database factories or the
existing isolated in-memory SQLite test fixture. No server port, external
service, existing database, real credential, or real email was used.

- `cd apps/api && ../../.venv/bin/pytest tests/test_telemetry.py tests/test_runtime_bounds.py tests/test_security.py -q --no-cov`
  — **53 passed**, no skips, one existing Starlette TestClient/httpx deprecation
  warning. This is a targeted check, not the full suite or a coverage gate.
- `.venv/bin/ruff check apps/api/app/runtime/telemetry.py apps/api/app/main.py apps/api/app/security.py apps/api/tests/test_telemetry.py`
  — passed.
- `.venv/bin/ruff format --check apps/api/app/runtime/telemetry.py apps/api/app/main.py apps/api/app/security.py apps/api/tests/test_telemetry.py`
  — passed.
- `MYPYPATH=packages/shared/python .venv/bin/mypy --config-file apps/api/pyproject.toml apps/api/app/runtime/telemetry.py apps/api/app/main.py apps/api/app/security.py apps/api/tests/test_telemetry.py`
  — passed, four source files.
- `node_modules/.bin/prettier --check docs/implementation/report11c-telemetry.md`
  — passed.
- `git diff --check` — passed.

The dedicated tests cover token-bearing actual candidate routes, unknown paths,
query strings, authorization/cookie/forwarded-IP/user-agent headers, bodies,
invalid and valid incoming request IDs, unique response/log correlation,
unhandled errors, early 408/413, cancellation/incomplete requests, non-HTTP
passthrough, registered-template snapshots/prefixes, response-header
replacement, release validation, and duration bounds. The first test iteration
caught lazy included routers incorrectly labeled `unmatched`; the route-context
fix passes against the actual candidate endpoint. An initial mypy invocation
without the shared-package path failed import resolution; the corrected explicit
command above passes. No failures remain in the scoped checks.

## Remaining acceptance

This completes only the authorized API correlation and completion-log slice.
Full 11C remains pending: hosted logging configuration and retention/access
controls, end-to-end ingress/web/provider redaction, actionable alert rules and
named responders, encrypted backups, recovery objectives and restore rehearsal,
and deletion replay after restore. Existing external logger behavior is not
certified by the completion payload tests. No third-party service, paid-provider
metric, financial metric, deployment, or full operations acceptance is claimed.
The coordinator remains sole integrator; hosted operations and the remaining 11C
acceptance work are the next eligible follow-up.
