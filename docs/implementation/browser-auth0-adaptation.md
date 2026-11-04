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
