# Existing-account production browser evidence

Verified 2026-11-04 in child checkout `AbhiNutakki/iopsych-accounts-browser`.
Application baseline: `b704965`. Tests, fixtures, and runner selector commit:
`0255fce`. No application code or migrations changed.

Live Orca terminal screen displayed `GPT-6-Astra medium fast`; no mode toggle
was performed. Read the accelerated implementation schedule, progress ledger,
and runner safety implementation. No applicable ancestor AGENTS.md was present;
the app-specific instructions do not govern these test/runner files.

## Changes and evidence

- Added `tests/browser/accounts.spec.ts` with three production Chromium tests.
  Admin discovery uses the visible Accounts link. Role change, deactivation,
  reactivation, and restoration assert exact PATCH bodies and incremented
  versions. An already-authenticated account observes its new role immediately,
  then receives 401 after deactivation; a fresh sign-in also receives 401 and
  installs no HttpOnly session cookie. Reactivation permits sign-in again.
- Verified administrator self controls are absent and direct self mutation is
  denied. Two browser pages exercise a real stale-version 409, disabled controls,
  explicit refresh, current values, and a subsequent successful update.
- Verified manager navigation omits Accounts, the direct page presents denial,
  and account discovery and mutation both return 403.
- Used keyboard traversal, Enter, Escape, cancellation focus restoration,
  confirmation focus, and success feedback focus. Five axe scans cover discovery,
  confirmation, inactive state, stale conflict, and manager denial.
- Added one independent synthetic account and a short-lived signed fixture token.
  Existing recruiter/manager identities are unchanged. Tokens remain within the
  owned runner and are redacted from diagnostics; no screenshots/traces retained.
- Coordinator approved the minimal runner selector in `msg_e46c4ab3f44f`.
  `scripts/browser-e2e.sh accounts.spec.ts` selects only known existing spec
  basenames; flags, paths, unknown names, and glob patterns fail before startup.
  No arguments still runs the full suite. Newly added spec basenames, including
  `invitation-issuance.spec.ts`, need no extra registration.

## Commands and results

- Normal checkout installation was finished before `npm ci --prefix tests/browser`:
  success, zero reported dependency vulnerabilities.
- `.venv/bin/pytest tests/browser/test_scaffold.py -q --no-cov`:
  **27 passed, zero skips**. This is the focused runner safety suite, not the
  application coverage gate. Ten added cases cover selector defaults/deduplication
  and unsafe argument rejection.
- `scripts/browser-e2e.sh accounts.spec.ts`: **3 passed, zero skips, 4.9 seconds**
  in the final browser phase. Runner first migrated a fresh PostgreSQL instance
  through `20261104_0010`, completed the shared and optimized Next.js production
  builds, and launched the real API and production web server.
- Chromium `156.0.8078.4`, axe `4.14.0`: **five scans, zero violations**.
  Color-contrast incompletes remain: discovery 4 nodes, confirmation 3, inactive
  state 5, stale conflict 5, manager denial 3. These are not passing manual checks.
- Standalone TypeScript check of `accounts.spec.ts` with `tsc --noEmit --target
  es2022 --module nodenext --moduleResolution nodenext --skipLibCheck`: passed.
- Prettier checks for the account spec/config, Ruff lint and formatting checks
  for the three Python files using `apps/api/pyproject.toml`, and `git diff
  --check`: passed.

The first browser run failed on test-side alert selectors also matching Next's
route announcer; its early failure left the target role changed and exposed a
follow-on test selection dependency. Scoped alerts to main and selected a
different stale role dynamically. The fresh final run passed all three cases;
no application bug was confirmed. There were no test skips or weakened retries,
worker limits, assertions, or runner safety checks.

## Isolation, handoff, and remaining gates

Used only allocated 3116/8116/5556 and local mailbox 1136/8136. Each run owned a
fresh unique Compose project/database and removed its servers, containers,
volumes, network, and temporary browser artifacts. All five ports passed the
runner's bind preflight after cleanup, and were released to invitation browser
dispatch `ctx_b08deb36ffed` in `msg_e32c9a2df48c`. The production build rewrote
`next-env.d.ts`; that generated change was restored, leaving no app edits.

No main edits, pushes, deployment, purchases, real mail, production secrets,
existing database reset, or use of protected ports 3000/8001/8000/5432 occurred.
No redundant full browser/application suite was run. No blocker remains for this
bounded task. Full package 7B/12A/12B acceptance, provider-based onboarding,
hosted validation, manual contrast/screen-reader/device checks, and intended-user
studies remain outside this evidence.
