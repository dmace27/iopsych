# Package 4C verification evidence

Executed locally on 2026-09-30 (America/Toronto), including PostgreSQL and the
production Next/FastAPI servers. A separate clean Linux run used CI's Node
22.23.3 and Python 3.12.14 runtimes, with fresh dependency installs. No tests
were skipped. This records actual local execution of the CI gates; a hosted
GitHub run has not been dispatched.

| Check                                                    | Result                                                                                                                                         |
| -------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| PostgreSQL 16 migration, seed, verification              | PASS in a disposable container on loopback; existing development database untouched                                                            |
| `npm run check` with PostgreSQL configured               | PASS: format, ESLint/Ruff, TypeScript/mypy, all tests and coverage gates                                                                       |
| Web Vitest                                               | 22 files, 99 tests passed; proxy and API-route security coverage gates at 100%                                                                 |
| Shared TypeScript Vitest                                 | 3 files, 99 tests passed                                                                                                                       |
| Shared Python pytest                                     | 93 tests passed                                                                                                                                |
| API pytest                                               | 129 tests passed, **zero skipped**, 100% application coverage; real PostgreSQL concurrent submission/report and retention locking tests passed |
| `npm run build`                                          | PASS: Next 16.3.6 production build with dynamic application routes and per-request CSP nonces                                                  |
| `npm run security:smoke`                                 | PASS: actual production web/API HTTP flow, described below                                                                                     |
| `npm audit --audit-level=high --json`                    | PASS: zero vulnerabilities                                                                                                                     |
| pip-audit 2.10.0, strict audit of installed Python graph | PASS: no known vulnerabilities                                                                                                                 |
| Gitleaks 8.24.3 full Git history and current source      | PASS with only the exact documented public test-key exception                                                                                  |
| Workflow definitions                                     | PASS: actionlint 1.7.7 validates both workflows                                                                                                |
| CI scanner installation command                          | PASS: pinned Go module builds in disposable Go 1.25 container                                                                                  |

## Production integration verification

`scripts/security_smoke.py` starts the built Next application and FastAPI on
loopback, creates a random isolated PostgreSQL schema, migrates it, seeds only
synthetic data, and issues ephemeral credentials. It verifies:

- Rendered script nonce matches the response CSP and changes on the next
  request; production eval/inline scripts are blocked, security headers are
  present.
- Sign-in requires the application origin and issues a Secure, HTTP-only,
  SameSite=Strict, root-path `__Host-` cookie with an eight-hour maximum
  lifetime.
- Unauthenticated internal access and cross-organization role access fail;
  cross-site internal mutations fail before upstream work.
- Candidate submission fails before consent, succeeds after affirmative consent,
  and returns only a score-free receipt.
- The internal proxy generates and reads the six-construct report using the
  approved synthetic role profile; report responses cannot be cached.
- Logout expires the browser cookie, and a request without it is unauthorized.
- The actual Uvicorn access formatter continues to work; process logs contain no
  raw invite/JWT credentials or signing keys and no logging errors.
- The real API peer budget throttles requests; sign-in, internal and candidate
  proxies all preserve 429, Retry-After and no-store.

The smoke check removes its own schema and process groups on success or failure.
It prints neither credentials nor candidate/report payloads.

## Saved evidence

[Linux checks](evidence/linux-checks.log),
[database setup](evidence/linux-database.log),
[production build](evidence/linux-build.log),
[production smoke](evidence/linux-production-smoke.log),
[npm audit](evidence/linux-npm-audit.json),
[Python audit](evidence/linux-python-audit.json),
[history secret scan](evidence/gitleaks-history.json), and
[current-source secret scan](evidence/gitleaks-source.json) record the results.
[Verification manifest](evidence/verification.json) identifies the checked
application files by hash. The full suite passed **420 tests with zero skips**
both locally and in the clean Linux environment.

## CI wiring

`.github/workflows/ci.yml` provisions PostgreSQL and runs migration/seed/verify,
all checks, the production build, and the production smoke check. It preserves
`checks.log`, `build.log`, and `production-smoke.log` as `application-checks`.

`.github/workflows/security.yml` runs blocking dependency and secret scans on
pull requests, main pushes, and manual runs with read-only repository access:

- npm audit blocks high/critical findings in the installed lockfile graph.
- A separate temporary pip-audit environment audits the installed Python graph,
  excluding only the editable local contracts package. `--strict` fails on
  collection errors; no advisory suppression is configured.
- Gitleaks builds from its pinned open-source Go module and scans full history
  (`fetch-depth: 0`). All default detectors remain enabled. The exact public
  synthetic fixture key is the sole exception; no files or rules are excluded.
- Redacted JSON reports are preserved as `dependency-scans` and `secret-scan`,
  including on failure, with 14-day artifact retention.

Pipeline commands use failure propagation (`pipefail` for tee-based logs).
Scanner/network failures fail the job. Hosted run URLs and artifact IDs can only
be produced after the changes run on GitHub; none are fabricated here.

## Repeat locally

Use an isolated PostgreSQL database, then run:

```sh
export DATABASE_URL=postgresql+psycopg://iopsych:iopsych@127.0.0.1:55434/iopsych
npm run db:migrate
npm run db:seed
npm run db:verify
npm run check
npm run build
npm run security:smoke
npm audit --audit-level=high
```

Run the scanner commands from the Security workflow for matching security gates.
The runtime bootstrap remains `npm ci` and `npm run api:install`. The smoke
script is included in repository lint/format/type checks.

Tool references: [pip-audit](https://github.com/pypa/pip-audit) and
[Gitleaks](https://github.com/gitleaks/gitleaks/tree/v8.24.3).
