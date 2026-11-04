# Package 6A — reproducible local setup

Implemented on worker branch `AbhiNutakki/iopsych-6a-setup`, based on
`a8de73c5c2d90fb085ef72e95555df8bdfda81e9`, November 4, 2026. Evidence below
covers the implementation in the commit containing this report. No main or
integration checkout was modified.

## Changes and contract coordination

- Setup uses `npm ci`; Python installation no longer eagerly upgrades all
  transitive dependencies or pip. README explains runtime and lockfile limits.
- The actual Bash launcher delegates to Python dotenv parsing, with shell
  execution and interpolation disabled and exported host/port/log overrides
  preserved. The retention statement is quoted. Paths work outside the repo
  working directory; loopback is the default listener.
- Dedicated Compose project `iopsych-6a`, volume, database `iopsych_6a`, and
  loopback PostgreSQL port 5541 avoid the existing service on 5432. Web/API use
  reserved 3101/8101. No existing database was reset or stopped.
- Added `POST /v1/auth/local-login`, accepting only `{"identity":"alpha"}` or
  `{"identity":"beacon"}` and returning a short-lived `access_token` to the
  local caller. Extra fields are rejected. The existing JWT verifier and
  database-authoritative authorization remain unchanged. Exact seed user ID,
  subject, email, and organization must match; roles still come from storage.
- Added `POST /api/session/local`, exchanging the fixed identity server-side
  into the existing HTTP-only, SameSite=Strict cookie for 15 minutes. Browser
  JavaScript receives only status, never the token. Same-origin POST is
  required. The sign-in page exposes a synthetic account selector only in
  opted-in development mode; provider integration remains outside 6A.
- Both opt-ins default off. API also requires explicit development environment,
  loopback peer and host, and configured local HTTP web origin; web requires
  development mode and local HTTP request/upstream origins. API launcher refuses
  a wildcard listener with local login enabled. Do not tunnel these dev servers.
- Coordinator approved the additive local contract before implementation through
  Orca ask, with the explicit-development and loopback-origin constraints
  applied. No shared schemas, migrations, scoring, scientific interpretation, or
  approval records changed. Existing seeded approval-shaped fixtures were not
  modified and are not evidence of real review.

## Verification

Environment: macOS, Node 24.21.0, npm 11.19.0, Python 3.12.16, Docker server
29.8.0, PostgreSQL 16.15 (`postgres:16-alpine`). Node 22 remains README
baseline.

| Command / check                                                                                                | Result                                                                                                                                  |
| -------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| Saved setup: `npm ci && PYTHON_BIN=python3.12 npm run api:install`                                             | Passed in this child worktree                                                                                                           |
| Updated `PYTHON_BIN=python3.12 npm run setup`                                                                  | Passed; lockfile unchanged                                                                                                              |
| `npm run db:up`                                                                                                | New isolated PostgreSQL container healthy                                                                                               |
| `npm run db:migrate`                                                                                           | All seven existing migrations applied to empty `iopsych_6a`                                                                             |
| `npm run db:seed` and `npm run db:verify`                                                                      | Two synthetic organizations, two roles, twelve ratings; tenant isolation passed                                                         |
| `pytest apps/api/tests/test_local_login.py apps/api/tests/test_launcher.py --no-cov` via `.venv/bin/python -m` | 14 passed                                                                                                                               |
| Full API suite with `TEST_POSTGRES_URL` targeting loopback 5541 / `iopsych_6a`                                 | 143 passed, zero skipped; 100% configured coverage                                                                                      |
| `npm run test --workspace @iopsych/web`                                                                        | 127 passed across 24 files; coverage gate passed                                                                                        |
| `npm run lint`                                                                                                 | Passed                                                                                                                                  |
| `npm run typecheck:api` and `npm run typecheck:js`                                                             | Passed                                                                                                                                  |
| `npm run format:check`                                                                                         | Passed                                                                                                                                  |
| Ruff and mypy on added launcher/verifier scripts                                                               | Passed                                                                                                                                  |
| `npm run build`                                                                                                | Shared package and production web build passed                                                                                          |
| `npm run dev`                                                                                                  | Actual API/web started on 127.0.0.1:8101 and 127.0.0.1:3101                                                                             |
| `.venv/bin/python scripts/verify-local-login.py` against running apps                                          | Both health routes, synthetic sign-in HTML, both cookie sessions, authenticated roles pages, cross-tenant 404s, and sign-out/401 passed |
| `git diff --check`                                                                                             | Passed                                                                                                                                  |

The launcher regression launches the committed shell/Python scripts with real
uvicorn and an isolated probe app, copying the actual dotenv template and adding
shell substitution text. It verifies the text remains literal, creates no shell
marker, preserves host/port overrides, and starts successfully from `/tmp`. The
subsequent live HTTP rehearsal exercises the real application and database.
PostgreSQL concurrency/retention tests use unique temporary schemas in the new
isolated database, then remove only those schemas.

## Limits, blockers, and handoff

No Docker, PostgreSQL, runtime, or 6A acceptance blocker remains. Initial full
API run had two PostgreSQL tests skipped before supplying the isolated URL; the
final run executed both successfully. FastAPI emits the existing httpx
TestClient deprecation warning. npm reports install-script approval warnings;
installation and all recorded build/runtime checks nevertheless succeeded.
`npm ci` also reports 15 dependency audit findings (11 moderate, 3 high, 1
critical) and an ESLint support warning against the unchanged lockfile;
remediation is outside 6A and remains a release/security follow-up.

No real browser automation, hosted deployment, provider authentication, mail
delivery, or extraction call was performed. HTTP integration plus component
coverage validates this package's session path; broader browser journeys belong
to later packages. Shared-contract suites were not separately rerun because no
shared contracts changed. Python transitive dependencies remain unlocked, as
already identified in `finish.md`. Only synthetic seed data was used; no email
was sent, no production secrets used, and no approval invented.

Development app processes were stopped after rehearsal. The isolated Compose
container/volume remains available for the coordinator; `npm run db:down` stops
only this project without deleting its data. Ignored dotenv files contain local
configuration and locally generated signing keys; none are committed.

Next eligible package: 6B product/interpretation decisions. Package 7A requires
the identity-provider decision from 6B as well as 6A; package 6C also awaits 6B.
