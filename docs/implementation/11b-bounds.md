# 11B early runtime bounds

This is a provider-independent early slice, not completion of phase 11B or a
hosted-readiness gate. Starting revision: `c20b3ed`. Worktree:
`iopsych-11b-bounds`. Reserved ports: 3117/8117/5557; reserved database:
`iopsych_bounds`. No existing database resets, external providers, public
services, or real candidate data are used.

## Setup

`npm ci && PYTHON_BIN=python3.12 npm run api:install` completed with exit 0.
Runtime versions: Node v24.21.0, npm 11.19.0, Python 3.12.16. npm reported 15
dependency vulnerabilities (11 moderate, 3 high, 1 critical); dependency
remediation is outside this worker's ownership and was not attempted.

## Scope and remaining gates

The approved implementation and focused verification results will be recorded
below before handoff. No migration or shared-package contract change is planned.

Full 11B remains open: hosted secret/public configuration validation; schema
compatibility checks; database connect/pool/statement deadlines; upstream/proxy
limits; shared ingress limits and fair per-browser budgets; general synchronous
work offloading; extraction retry/output/cost/concurrency and duplicate
controls; real configured-provider synthetic staging checks. No product,
scientific, provider, or deployment approval is inferred.

## Approved contract and implementation

Coordinator approved through `orca orchestration ask` before global changes:
preserve `/health`; add a DB-only `/ready`; default body limit 1 MiB and total
upload deadline 30 seconds; no duplicate environment-mode field. This approval
is for the early engineering contract only.

- `GET /health` retains its exact status/service/version JSON and never queries
  the database.
- `GET /ready` performs `SELECT 1` in a synchronous FastAPI endpoint (worker
  thread), using an isolated session context that closes/rolls back on exit.
  Success is HTTP 200 with `{"status":"ready","service":"api"}`; SQLAlchemy
  failures are HTTP 503 with `{"status":"unavailable","service":"api"}`.
  Responses expose no database address, credentials, exception, or provider
  configuration and retain security/no-store headers. No paid probes occur.
- `RequestBodyLimitMiddleware` runs inside existing security/rate middleware and
  outside audit/routes. It counts actual ASGI body bytes, ignoring
  Content-Length as authority, including absent/misleading lengths and chunked
  uploads. Exactly-at-limit input is accepted. Excess produces problem JSON 413
  with code `request_body_too_large`; exceeding the total body-read deadline
  produces 408 with code `request_body_timeout`. Both include existing security
  headers, omit token-bearing paths and body contents, and occur before route or
  database side effects. There is no existing correlation-ID middleware to
  replace; future outer correlation middleware can wrap these responses.
- A partial disconnect stops processing without invoking routes or writing a
  response. Cancellation propagates. Non-HTTP ASGI scopes pass through.
- Accepted uploads replay intact once. A bytearray avoids storing an unbounded
  list of empty/tiny chunks. Memory is proportional to the configured limit,
  with a transient copy during replay plus the ASGI server's current chunk; this
  is not a process-wide memory or concurrency limit.

No schema migration, auth configuration, frontend, provider, deployment,
assignment/scoring, dependency, or progress-ledger edits were made.

## Local and hosted configuration

Both local and hosted processes use the same validated `RUNTIME_` variables,
read from process environment or `apps/api/.env`:

| Variable                               | Default | Allowed range         |
| -------------------------------------- | ------- | --------------------- |
| `RUNTIME_MAX_REQUEST_BODY_BYTES`       | 1048576 | 1–16777216 bytes      |
| `RUNTIME_REQUEST_BODY_TIMEOUT_SECONDS` | 30      | 1–120 seconds, finite |

Invalid values fail application construction. Values cannot disable bounds. The
body limit is bytes, not characters: JSON escaping and metadata count too. The
default accommodates the current browser's UTF-8 job-description inputs; callers
with unusually expanded JSON must remain within the configured limit. Tests can
inject `RuntimeSettings` through the additive factory argument.

For local development these defaults require no new secrets, database setup, or
mode toggle. For hosted use, configure ingress/server body, upload, header,
connection and concurrency limits and proxy deadlines as well; the middleware
cannot bound allocations before the ASGI server delivers a chunk, an upstream
proxy's buffering, or unlimited simultaneous requests. Rejected uploads are not
drained by application code; HTTP framing, connection closure/reuse and
backpressure remain server/ingress responsibilities. The upload deadline ends
before route execution and is not a request, provider, or DB query timeout.

**Readiness limitation:** this probe is DB-connectivity-only, not a deployment
traffic-admission gate. It does not validate migrations, credentials for other
services, grants beyond `SELECT 1`, or hosted settings. DB pool/connect/query
waits retain existing configuration and can still stall threads or exhaust pool
capacity. Offloading protects the event loop but does not cancel blocking DB
work. Complete driver/pool/statement deadlines and schema verification in a
coordinated later slice before relying on readiness for hosted admission.

## Verification

All checks used this child worktree, synthetic fixtures and in-memory SQLite; no
network services or databases were started and ports 3000/8000/8001 were
untouched. Allocated 3117/8117/5557 were not needed. This is ASGI/in-process
evidence, not real ingress, PostgreSQL, or staging evidence.

- Setup command above: exit 0.
- `.venv/bin/python -m pytest -c apps/api/pyproject.toml apps/api/tests/test_runtime_bounds.py apps/api/tests/test_health.py apps/api/tests/test_security.py apps/api/tests/test_roles_api.py apps/api/tests/test_invitations.py --no-cov`:
  41 passed, zero skips (before adding the separate fully stalled upload case).
  Existing role/invitation authentication, audit and payload behavior passed.
- Initial targeted mypy without shared source path failed to resolve
  `iopsych_contracts` (17 resulting import/type errors); this was an invocation
  issue.
  `MYPYPATH=packages/shared/python .venv/bin/python -m mypy --config-file apps/api/pyproject.toml apps/api/app/runtime apps/api/tests/test_runtime_bounds.py apps/api/app/main.py`:
  passed, six source files.
- `.venv/bin/python -m ruff check --config apps/api/pyproject.toml apps/api/app/runtime apps/api/tests/test_runtime_bounds.py apps/api/app/main.py`:
  passed. Initial long test lines were fixed with Ruff format.
- `.venv/bin/python -m ruff format --config apps/api/pyproject.toml apps/api/app/runtime apps/api/tests/test_runtime_bounds.py apps/api/app/main.py`:
  final pass left six files unchanged.

New tests cover multi-chunk exact/excess byte limits, missing/understated/
overstated Content-Length, chunked encoding, UTF-8 bytes, empty chunks,
disconnects, cancellation, non-HTTP pass-through, total trickle/stall deadlines,
validated env configuration, DB success/failure privacy and session cleanup,
unchanged liveness during a blocked probe, JSON replay, and rejection before DB
work. The TestClient emits the existing httpx deprecation warning; no dependency
changes were made to suppress it.

- Final focused coverage command:
  `.venv/bin/python -m pytest -c apps/api/pyproject.toml apps/api/tests/test_runtime_bounds.py --cov-reset --cov=app.runtime --cov-branch --cov-report=term-missing --cov-fail-under=100`:
  **17 passed, zero skips, 100% statements and branches** for the new runtime
  modules (68 statements, 12 branches); exit 0. This is not whole-application
  coverage or completion of 11B.
- `npx prettier --write docs/implementation/11b-bounds.md` and
  `git diff --check`: passed before commit.

Next eligible work is coordinator review/integration of this slice and
separately allocated database/schema/ingress/provider hardening. The remaining
full-package gates above are explicit blockers to claiming full 11B acceptance,
not blockers to integrating this approved bounded slice.
