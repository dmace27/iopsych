# Synthetic browser authentication adaptation

Prepared against child baseline `124f887`; integrated browser runtime pending.
Live Orca terminal showed `GPT-6-Astra medium fast`; no toggle was made. Saved
setup processes were finished before checks; no existing database or protected
port was used.

All seven browser specifications now establish synthetic sessions through a
browser same-origin `POST /api/session` with JSON `{ token }`, expecting 200.
The shared helper navigates explicitly after exchange; it does not claim to test
Auth0 callback navigation. Disabled-account and invalid-token exchanges retain
401/no-cookie assertions, empty tokens retain 400, and the production sign-in
screen must have no token input. Candidate, privacy, invitation, account, cookie,
sign-out and axe checks remain; retired token-form keyboard assertions now cover
the public skip link and synthetic exchange recovery instead.

The runner explicitly sets `ENABLE_TOKEN_SIGN_IN=true`, `AUTH_PROVIDER=hmac`,
and its owned loopback `APP_BASE_URL`. Child environment isolation excludes
Auth0/Resend settings; inherited Auth0/app-origin/token-opt-in settings fail
preflight. Fresh generated HMAC keys and deterministic local mail/extraction
remain the only fixture providers. No application or dependency files changed.
Read remote `docs/identity.md` at `646201a` and installed Next route/cookie docs.

Checks:

- `npm ci --prefix tests/browser`: passed, 6 audited packages, zero vulnerabilities.
- `.venv/bin/python -m pytest -q -o addopts='' tests/browser/test_scaffold.py`: 32 passed.
- `.venv/bin/python -m ruff check --config apps/api/pyproject.toml scripts/browser-e2e.py tests/browser/test_scaffold.py`: passed.
- `.venv/bin/python -m ruff format --check --config apps/api/pyproject.toml scripts/browser-e2e.py tests/browser/test_scaffold.py`: passed.
- `node_modules/.bin/tsc --noEmit --strict --target ES2022 --module ESNext --moduleResolution Bundler --skipLibCheck --types node tests/browser/*.ts`: passed.
- `npm --prefix tests/browser test -- --list`, with `BROWSER_E2E_OWNED=1` and all twelve required fixture variables set to `synthetic-discovery-only`: 47 tests discovered in seven files; no services started.
- `node_modules/.bin/prettier --check tests/browser/auth.ts tests/browser/*.spec.ts`: passed.
- `git diff --check`: passed.

Awaiting coordinator reconciled HEAD and exact session-contract confirmation
before the single combined production-browser run on exclusive ports
3116/8116/5556/1136/8136. These focused results are not browser execution,
live Auth0/Resend acceptance, hosted HTTPS evidence, or manual accessibility approval.

## Reconciled-contract preparation

Coordinator confirmed the Auth0 owner agrees with the exact exchange contract.
Service policy changed after the first commit: Standard/default only; the live
terminal no longer displays Fast and no worker toggle was made.

Inspection of reconciliation commit `aeb7584` confirms newly generated reports
use algorithm 2.0.0 with retained v1 assignments/scoring. Smoke now asserts the
actual generated result uses the direct structure target, and the actual trace
response has algorithm 2.0.0, trace/scoring 1.0.0, all six matching question
selection versions, and the frozen legacy definition hash. Both browser specs
read the retained definition fixture instead of the mutable current definition.
Strict TypeScript and scoped Prettier checks passed after these assertions.
This prepares current-v2 browser evidence; it does not claim browser replay of
an existing persisted v1 report (separate backend compatibility tests cover it).

## First actual combined run (failed)

`f918bbb` merges coordinator-approved aggregate `ad06206` with browser assertion
commit `ff7c247`. After successful `npm ci` and
`PYTHON_BIN=python3.12 npm run api:install`, `bash scripts/browser-e2e.sh`
passed the production build and fresh PostgreSQL migrations through0012, then
ran47 Chromium156.0.8078.4 cases: **37 passed,10 failed, zero skipped (3.2m)**.
Compact axe evidence is in `tests/browser/evidence/auth0-aggregate-initial.json`.
Owned containers/network and temporary artifacts were removed after failure.

Six failures reproduce axe `label-content-name-mismatch` on version buttons:
three profile viewport cases, draft keyboard, recruiter extraction, manager
profile. Coordinator owns the app fix; the axe checks are unchanged.
Other failures: renamed invitation state copy, shared privacy invite already
anonymized by another spec, and missing revocation/pagination controls around a
confirmed shared-peer429. New v2 result/direct target/trace provenance passed.

Fixture repair uses a distinct HISTORY invite and exact invitation discovery,
updates state copy and actual pagination counts, and executes each spec once
with61s rate-window separation in the same owned build/database. The real
300/min API limiter is unchanged; failures still collect and fail the runner.
Focused runner checks now **34 passed**; strict browser TypeScript, scoped
Prettier, Ruff checks/format and diff checks pass. No new browser pass is claimed
until the app repair and packaging build-slot handoff permit the affected-spec
rerun. Green accounts/issuance cases are not scheduled for duplicate execution.
