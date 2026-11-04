# Package 6A boundary fixes

Implemented November 4, 2026 in the dedicated `iopsych-6a-boundary-fix`
worktree, addressing both findings in `6a-review.md`. This report is committed
with the implementation and tests; use its containing commit as the evidence
revision. No shared contracts, migrations, dependency files, broader session
helpers, or progress ledger were changed.

## Changes

The local session route now requires a present actual `Host` authority matching
`localhost` (case insensitive), `127.0.0.1`, or bracketed `::1`, optionally with
a numeric port in 1–65535. Missing, nonlocal, malformed, URL-like, alternate
IPv4, and forwarded-only authorities fail before upstream access or cookie
creation. This check is independent of Next's normalized request URL; the
existing URL, upstream configuration, development opt-in, and same-origin checks
remain. Neither `X-Forwarded-Host` nor `Forwarded` supplies trusted authority.

The API launcher uses Pydantic's `TypeAdapter(bool)` so its opt-in
interpretation matches `AuthenticationSettings.local_login_enabled`. All
accepted true forms trigger the loopback-listener guard. False forms and an
absent setting preserve normal startup; invalid values stop before `execv` with
a generic error that does not echo configuration contents. Existing dotenv and
exported-override behavior is preserved.

Tests cover normalized loopback URLs paired with hostile actual Host, matching
Origin and Fetch Metadata fallback, malformed authorities, forwarding spoofing,
valid authorities, Pydantic parity, nonlocal listeners, invalid booleans, and
loopback startup. The actual launcher regression uses allocated port 8113
instead of another worker's 8101. A standalone live Next regression is retained
alongside route tests and cleans up its own server process group and mock API.

## Commands and results

Saved setup was already present. Verified installed setup rather than repeating
installation: `npm ls --depth=0` exited 0 with the workspace dependency tree;
`.venv/bin/python --version` returned Python 3.12.16;
`.venv/bin/python -m pip check` exited 0 with no broken requirements. The saved
setup command remains `npm ci && PYTHON_BIN=python3.12 npm run api:install`;
this fix run did not rerun that installation or claim a new fresh-checkout setup
rehearsal.

Run from the repository root:

```sh
npm exec --workspace @iopsych/web -- vitest run app/api/session/local/route.test.ts --coverage.enabled=false
.venv/bin/python -m pytest -c apps/api/pyproject.toml apps/api/tests/test_launcher.py --no-cov -q
.venv/bin/python apps/web/app/api/session/local/route.live-test.py
.venv/bin/python -m ruff check --config apps/api/pyproject.toml scripts/run-api.py apps/api/tests/test_launcher.py apps/web/app/api/session/local/route.live-test.py
.venv/bin/python -m ruff format --check --config apps/api/pyproject.toml scripts/run-api.py apps/api/tests/test_launcher.py apps/web/app/api/session/local/route.live-test.py
npm exec --workspace @iopsych/web -- eslint app/api/session/local/route.ts app/api/session/local/route.test.ts --max-warnings=0
npx prettier --check apps/web/app/api/session/local/route.ts apps/web/app/api/session/local/route.test.ts docs/implementation/6a-fixes.md
git diff --check
```

Final results: 52 route tests passed, 104 launcher tests passed, all five live
HTTP scenarios passed, and scoped lint/format/diff checks passed. Coverage gates
were disabled for these targeted subsets; no full-suite or release coverage
claim is made. The first launcher run had 68 passes and 36 failures from an
incorrect argv index in the new test assertion; the assertion was corrected to
locate `--host`, and the rerun passed all 104. Ruff initially flagged list
concatenation in a parametrization; corrected to unpacking and rechecked clean.

The live script starts `npm run dev:web` with `LOCAL_LOGIN_ENABLED=true`,
`WEB_HOST=127.0.0.1`, `WEB_PORT=3113`, and `API_BASE_URL=http://127.0.0.1:8113`.
Its loopback mock returns a synthetic placeholder, counts POSTs, and does not
connect to any database. Requests all connect directly to 127.0.0.1; invalid
domains appear only in headers.

| Scenario                                                    | HTTP | Cookie present | Upstream POST count delta |
| ----------------------------------------------------------- | ---- | -------------- | ------------------------- |
| Loopback Host with matching Origin                          | 200  | yes            | 1                         |
| Hostile Host with matching Origin                           | 404  | no             | 0                         |
| Hostile Host with same-origin Fetch Metadata, no Origin     | 404  | no             | 0                         |
| Hostile Host and matching Origin, forged forwarding headers | 404  | no             | 0                         |
| Loopback Host with hostile Origin                           | 403  | no             | 0                         |

## Remaining work and limits

No blocker remains for these two scoped fixes. Coordinator integration and
independent re-review remain; this report does not independently close full 6A
setup acceptance or any later package. No database was started or reset;
reserved DB 5553 / `iopsych_6afix` was unused. Ports 3000, 8000, and 8001 were
untouched. Live test processes were stopped. No public deployment, push,
provider call, real email, secrets, product decision, or scientific approval was
involved.
