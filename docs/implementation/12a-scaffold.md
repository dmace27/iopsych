# Package 12A: early browser runner scaffold

This closes only the assigned early scaffolding slice. **Full 12A acceptance is
open.** No hosted release, real-provider, scientific, privacy, or pilot approval
is claimed. No required journey tests are marked skipped to manufacture success.

## Revision and environment

Verified implementation: `cc2bb409997fb10309b8c6be5e47dac011c4f648`, based on
integration `8450a09`. This report is a subsequent documentation-only commit.
Verification date: November 4, 2026, macOS arm64, Node 24.21.0, npm 11.19.0,
Python 3.12.16, Docker Engine 29.8.0, Next.js 16.3.8 production webpack build,
Playwright 1.64.1 Chromium 156.0.8078.4, axe Playwright 4.14.0.

Container image evidence (Compose uses tags, so future pulls can differ):

- PostgreSQL `postgres:16-alpine`, digest
  `sha256:721873c34ceb9f8d8fc265984940dc982404c105f19ad51be9fdc5970a6080ea`.
- Mailpit `axllent/mailpit:v1.27.10`, digest
  `sha256:b1f1be18af530d939a11ee8820b379e0c88eeec204d904bfad68862adced3a5a`.

## Running it

Use a dedicated checkout with no local `.env*` files except examples. Docker
must use a local Unix-socket context. Keep ports 3104, 8104, 5544, 1124, and
8124 free. The runner deliberately refuses inherited
database/API/auth/invite/extraction/ SMTP/mail/public-browser/Docker/Compose
configuration and HTTP proxy variables; unset them in the invoking shell,
without copying production secrets here.

```sh
npm ci && PYTHON_BIN=python3.12 npm run api:install
npm --prefix tests/browser ci
npm --prefix tests/browser run install:browser
.venv/bin/python -m pytest -q -o addopts='' tests/browser/test_scaffold.py
scripts/browser-e2e.sh
```

Linux hosts may additionally need Playwright's documented Chromium OS packages.
The standalone browser manifest and lockfile do not change the root workspaces
or root manifests. Invoke the wrapper from any directory; directly running
`npm --prefix tests/browser test` fails without runner-owned fixture settings.
There is no existing-stack or arbitrary-target mode.

Each run creates a UUID-named Compose project with a fresh `iopsych_e2e`
PostgreSQL database backed by tmpfs, applies all seven migrations, and seeds
only synthetic records. It never drops, resets, or attaches an existing
database. Database and SMTP/HTTP mailbox publishing use `127.0.0.1:5544`,
`:1124`, and `:8124`; Uvicorn and production `next start` bind `127.0.0.1:8104`
and `:3104`. Ports 3000/8000/8001/5432 and other workers' services are
untouched.

The runner builds through `npm run build` on every run. Next may regenerate the
tracked `apps/web/next-env.d.ts` paths; that generated diff was restored after
verification and is not part of this change. Do not run concurrently with a dev
server/build in the same checkout.

## Implemented checks and fixtures

- Real Chromium loads web health and confirms the internal roles boundary
  returns 401 without a session.
- Public sign-in renders, rejects an invalid synthetic credential, stays on
  sign-in, and establishes no cookies. No Secure-cookie header injection or
  session bypass is used.
- A real database-backed invitation renders consent with no question radios;
  valid-shaped submission before consent returns 409. Decline renders its
  terminal state, survives browser refresh, and still exposes no question
  radios.
- Axe scans sign-in, consent, and declined screens with WCAG 2 A/AA, 2.1 A/AA,
  and 2.2 AA tags. Violations fail the tests; none are suppressed.
- Thirteen focused Python cases verify rejection of inherited remote targets,
  remote Docker contexts, local dotenv files, occupied ports, and real email
  recipients, plus deterministic schema-valid extraction fixture behavior.
- The test-only ASGI factory uses the existing application factory seams to
  inject deterministic extraction and local SMTP delivery. Extraction accepts
  only `fixtures.JOB_DESCRIPTION`; ratings are synthetic plumbing data and
  retain `needs_human_review=true`. This is not a real extraction-provider test.
- The runner directly creates one synthetic invite, sends the application's
  rendered invitation through SMTP to Mailpit, and verifies one captured
  message. This establishes mailbox plumbing, not browser invitation issuance or
  a production email-provider acceptance claim.

All browser requests are restricted to the fixed local web origin, service
workers are blocked, and extraction never calls a hosted provider. SMTP accepts
only `@example.invalid` recipients and always connects to loopback port 1124.
Mailpit has no configured relay. The container bridge is ordinary Docker
networking with loopback publishing, not a network-level egress sandbox.

The runner stops its process groups and removes only its unique Compose project
on normal completion, errors, Ctrl-C, and SIGTERM. SIGKILL or machine failure
cannot execute cleanup; inspect the exact `iopsych-e2e-<run-id>` project before
manually removing stale resources. A subsequent run refuses occupied ports. It
does not kill or reuse whatever currently owns a port.

Temporary server logs and browser error artifacts are deleted on exit; traces,
screenshots, and video are disabled. Captured browser console output redacts the
run's invite token and signing secrets before printing. Credentials are
generated per run; no real credentials or email are required.

## Results

| Command/check                                                          | Result                                                                                       |
| ---------------------------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| Saved setup hook `npm ci && PYTHON_BIN=python3.12 npm run api:install` | Passed                                                                                       |
| `npm --prefix tests/browser ci` and browser install                    | Passed                                                                                       |
| Focused pytest command above                                           | 13 passed, zero skips                                                                        |
| `scripts/browser-e2e.sh`                                               | Passed: production build, seven fresh migrations, SMTP capture, 3 Chromium tests, zero skips |
| Automated axe checks                                                   | Zero violations on the three scanned screen states                                           |
| Ruff check and format check on the three owned Python files            | Passed                                                                                       |
| Prettier check on browser JSON/TypeScript/YAML                         | Passed                                                                                       |
| `bash -n scripts/browser-e2e.sh`; `git diff --check`                   | Passed                                                                                       |
| Post-run listeners on all five reserved ports                          | None; owned project containers/network removed                                               |

The first development run found an ESM discovery error; setting the standalone
package to module fixed it. An attempted Docker `internal` network prevented
published ports on this Docker Desktop runtime; it was removed, and SIGTERM
cleanup was verified during that failed attempt. The final full run passed in a
fresh project, with the three Chromium tests taking 4.7 seconds after startup.

Root `npm ci` reported **15 vulnerabilities: 11 moderate, 3 high, 1 critical**.
They are existing root dependencies, not resolved by this ownership-limited
change. The standalone browser install reported zero vulnerabilities. These
install summaries are not refreshed dependency/history secret-scan acceptance.

## Required follow-up integration

1. Integrate the 6A local sign-in/startup contract before adding authenticated
   browser tests. Add distinct recruiter, hiring-manager, and administrator
   accounts and browser contexts; the existing seed has two recruiter tenants,
   and this scaffold exercises neither a successful login nor manager/admin
   work.
2. Once feature packages are integrated, cover the entire browser role creation,
   extraction, edit/approval, invite issuance/mailbox-link opening, assessment,
   report/evidence, export/download, native-dialog, deletion, and rights
   journey. Add authorization/tenant/approval/expiry/revocation/failure
   negatives and populated migration, historical-version, and
   browser-persistence upgrades.
3. Add hosted CI and required branch checks under their owners. This change does
   not modify CI. Preserve zero required skips and attach revision-linked
   results.
4. Verify real HTTPS cookie/CSP behavior in staging with normal browser cookie
   handling. Loopback HTTP negative checks do not establish TLS or successful
   secure-session behavior. Run real configured email/extraction providers
   separately with controlled synthetic inputs and explicit authorization.
5. Expand axe coverage to all screens and pair it with the 12B manual keyboard,
   screen-reader, contrast, zoom/reflow, touch, reduced-motion, and user-study
   work. Three automated screen scans are not WCAG conformance or comprehension/
   completion-time evidence.
6. Refresh dependency/history secret scans and hosted operational/release
   checks. No push, deployment, scientific policy changes, or pilot approval
   occurred.
