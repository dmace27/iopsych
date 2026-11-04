# 12A expanded local browser evidence

Date: 2026-11-04. Application baseline: `c20b3ed`; test implementation:
`7589fd4ba45cb254d45bfb1fe6179fb01b0efc2f`. Child branch:
`AbhiNutakki/iopsych-12a-expand`.

The bounded expansion is implemented, but **the browser gate is red and full
12A/12B acceptance remains open**. Production Chromium reproduced two profile
contrast failures and a sign-out failure. These application changes belong to
other workers; assertions remain enabled, without exclusions or expected-failure
annotations. No provider login, manager handoff, scientific approval, invitation
UI, hosted HTTPS, or real-pilot readiness is claimed.

## Coverage and fixture boundary

The runner owns a fresh Compose project, PostgreSQL tmpfs, and Mailpit with no
forwarding. Allocation is web 3116, API 8116, database 5556, SMTP 1136, Mailpit
HTTP 8136, all loopback. Existing services and ports 3000/8000/8001 are
untouched. Every run applies migrations to its new database and tears down only
its own project, even after failed assertions. Browser requests are restricted
to the owned web origin; server extraction uses the existing deterministic
fixture.

The fixture now creates four independent invitations (decline, normal storage,
getter denial, quota denial) against the existing synthetic seeded profile. It
captures exactly four local messages. It adds one explicit synthetic Alpha
administrator, fixed ID ending `0099`, without changing production seed users or
permissions. Recruiter and manager remain the existing Alpha and Beacon seed
identities. Short-lived JWTs are minted only in `tests/browser/fixtures.py`
using the runner's ephemeral signing secret. The normal verifier, database
permissions, token-entry UI, session exchange, Secure/HttpOnly/Strict cookie,
and production Next proxy remain in use. No verifier bypass or test endpoint was
added. This is synthetic session coverage, not provider-login coverage.

Ten browser cases cover:

- Health and unauthenticated internal rejection; accessible sign-in and invalid
  credential rejection.
- Consent gating, rejected pre-consent submission, decline and reload.
- Recruiter role list/create form, actual role creation, deterministic draft
  extraction, saved version 2 alongside version 1, and reload persistence.
  Recruiters cannot see approval controls; no approval is performed.
- Separate manager tenant list, no role-create control, cross-tenant role,
  profile and assessment reads denied, extraction mutation denied, unavailable
  role recovery, own approved-profile view, privacy UI/API denial and sign-out.
- Actual UI selection/submission in normal, denied-storage getter and
  quota-failure browsers; truthful unsaved status, normal draft reload/resume,
  review and completion, completion reload without radios, and only an
  answer-free receipt remaining on the normal device.
- Real generated report and saved-report reload; native evidence dialog opens,
  focuses Close, closes with Escape, and restores the trigger focus.
- Synthetic administrator privacy screen, real JSON download (deleted without
  retaining payload), confirmation, anonymization of the quota fixture, removal
  of export affordance and subsequent export rejection with HTTP 410.

This is a single-worker ordered scenario: report and privacy cases consume the
preceding real candidate submissions. Run the owned runner as a whole; selecting
those cases alone would omit their setup. Screenshots, video and traces remain
disabled; temporary Playwright diagnostics/server logs/downloads are removed.
Generated bearer credentials are redacted before stdout is printed. Durable axe
evidence contains only static test names, engine, rule IDs and node counts,
never HTML, tokens, invitations, exports or raw answer payloads.

## Reproduced blockers

| Finding                    | Actual observation                                                                                       | Required integration action                                                                                                                                          |
| -------------------------- | -------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Editable profile contrast  | Axe `color-contrast`, serious, six construct-number spans matching `fieldset > legend > .text-slate-400` | UI owner adjusts contrast and reruns these assertions.                                                                                                               |
| Read-only profile contrast | Axe `color-contrast`, serious, six construct eyebrow labels matching `article ... .text-slate-400`       | UI owner adjusts contrast and reruns these assertions.                                                                                                               |
| Production sign-out        | Browser `DELETE /api/session` returns 204, then `GET /api/internal/roles` returns 200 instead of 401     | Session owner investigates deletion of the production `__Host-` Secure cookie; missing Secure deletion attributes are a source-level hypothesis, not a verified fix. |

Axe uses WCAG 2.0/2.1 A/AA and 2.2 AA tags with no rule exclusions. Soft axe
assertions deliberately allow the remaining functional steps to execute but
still fail their test and the runner. Incomplete rules require manual review;
zero violations elsewhere is not a conformance claim. Neither manual assistive
technology nor intended-user comprehension/timing testing was performed.
Findings were escalated through Orca messages `msg_9f620af63b4a` and
`msg_98ab552eb45e` for separately owned fixes.

## Commands and results

Environment: macOS, Node 24.21.0, npm 11.19.0, Python 3.12.16, Playwright
1.64.1, Chromium, PostgreSQL 16 Alpine, Mailpit 1.27.10, production Next 16.3.8.

| Command                                                                                                                                       | Result                                                                                                                                                                                   |
| --------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `npm ci && PYTHON_BIN=python3.12 npm run api:install`                                                                                         | Exit 0; saved setup completed. npm reported 15 existing vulnerabilities (11 moderate, 3 high, 1 critical); dependency remediation is separately owned. No root manifests/locks changed.  |
| `npm ls --depth=0 --workspace @iopsych/web` and `.venv/bin/python -m pip check`                                                               | Exit 0; dependencies resolve and no broken Python requirements.                                                                                                                          |
| `npm --prefix tests/browser ci`                                                                                                               | Exit 0; five test-tool packages installed, zero reported vulnerabilities.                                                                                                                |
| `.venv/bin/python -m pytest tests/browser/test_scaffold.py -o addopts='' -q`                                                                  | 17 passed; inherited targets/proxies, remote Docker, dotenv, occupied ports, exact allocation, synthetic mail/extraction, fixture guard, real JWT verification and diagnostic redaction. |
| `.venv/bin/python -m ruff check --config apps/api/pyproject.toml tests/browser/*.py scripts/browser-e2e.py`                                   | Exit 0 after formatting/import cleanup.                                                                                                                                                  |
| `bash scripts/browser-e2e.sh`                                                                                                                 | Production build/migrations/local mail and actual browser subset executed; final results recorded below. Nonzero status is preserved for the application failures.                       |
| `node_modules/.bin/prettier --check tests/browser/*.ts tests/browser/compose.yaml docs/implementation/12a-expanded.md` and `git diff --check` | Final formatting/whitespace verification recorded with handoff.                                                                                                                          |

Earlier iteration: 6 passed/3 failed; two profile contrast failures plus an
incorrect report-heading selector in the new test. The selector was corrected to
the current candidate-specific heading. One attempted rerun failed during build
because dependency installation overlapped it; cleanup succeeded and the run was
repeated after setup completed. Subsequent runs passed all report and privacy
assertions and reproduced the sign-out defect. No failing application assertion
was relaxed to obtain a green result. Production builds regenerate
`apps/web/next-env.d.ts`; that generated diff was restored, not committed.

## Final retained result

The final command `bash scripts/browser-e2e.sh` exited 1: **8 passed, 2 failed,
0 skipped in 24.1 seconds**. All functional steps except sign-out passed; the
two failed cases also retain the editable/read-only profile contrast assertions.
The production build and fresh seven-migration database setup succeeded. Cleanup
removed both owned containers and their network.

[Sanitized machine evidence](../../tests/browser/evidence/12a-expanded.json)
records the exact implementation revision and 24 axe scans using axe 4.14.0. Two
scans report six serious contrast nodes each; 23 scans have incomplete
color-contrast checks requiring manual review. Scan order within each test
matches the `accessible(page)` call order in the committed test. No raw axe HTML
or candidate data is retained. Final Ruff, Prettier and `git diff --check` all
exited 0. The report/evidence commit follows the implementation commit so its
source revision is stable and reviewable.

## Integration adaptation and remaining gates

The backend 6C and candidate UI work were not merged into this child tree and
never shared its database. This fixture still uses the current v1 definition and
`AssessmentInvite` constructor. When 6C lands, explicitly bind each fixture
invitation to the agreed immutable assessment/scoring versions and synthetic
purpose using its supported contract, and consume the consent-gated assigned
definition in candidate checks. Do not mark an unreviewed definition reviewed,
reuse another worker's database, invent scientific approval, or silently omit
new required fields. Retain the previous-version scenario separately; this run
covers fresh migrations, not populated version upgrades.

Additional package gates remain provider login, same-tenant recruiter/manager
handoff and approval, invitation management, expiration/revocation/skips and
retry/idempotency expansion, full privacy lifecycle, historical upgrades, real
TLS cookie/CSP behavior in staging, configured-provider smoke, hosted required
checks and human accessibility/usability evidence. Loopback Chromium accepting
Secure cookies does not establish remote HTTPS behavior. No full test suite,
public deployment, push, real email/provider call, secret scan or purchase was
performed. `docs/implementation/progress.md` remains coordinator-owned.
