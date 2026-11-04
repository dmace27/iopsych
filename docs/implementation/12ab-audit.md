# 12A/12B evidence and coverage audit

Audit date: 2026-11-04. Source revision:
`a8de73c5c2d90fb085ef72e95555df8bdfda81e9`. Worker branch:
`AbhiNutakki/iopsych-12ab-audit`; child checkout only.

## Conclusion and scope

Neither 12A nor 12B is complete. Existing tests provide useful component/API
evidence, but no committed production browser runner or complete
accessibility/usability evidence was found. This report changes no application,
test, dependency, contract, migration, scientific interpretation, or approval.
It maps every 12A/12B scope and acceptance item in
`final-implementation-plan.md`, with the expanded negatives in `finish.md` tasks
14–15 and all ten screens in `mvp-spec.md` section 11.

Evidence labels below: **executed** means this audit ran the stated command;
**static** means inspected source/tests, not observed browser behavior;
**historical** means a previously recorded result, not rerun here; **missing**
means no corresponding implementation/evidence found in the inspected tree. A
component test using keyboard events is not manual keyboard or screen-reader
evidence. No browser/device, screen reader, intended-user study,
configured-provider request, real email, hosted workflow, deployment, or
database reset was exercised here.

Read repository plans/specification and `apps/web/AGENTS.md` (the only
discovered AGENTS file; no applicable ancestor file was present). Its Next
documentation requirement applies before code changes; this task makes
documentation changes only.

## Executed evidence and runtime prerequisites

| Command/check                                                                                     | Result and limits                                                                                                                                                                                             |
| ------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `git log -1 --oneline`; `git merge-base HEAD a8de73c`; initial `git status --short`               | HEAD and merge base were `a8de73c`; clean child worktree.                                                                                                                                                     |
| `node --version`; `npm --version`; `python3.12 --version`                                         | Node v24.21.0, npm 11.19.0, Python 3.12.16, Darwin. Node meets root `>=22` engine but differs from `.nvmrc`/CI Node 22; Python matches `.python-version` 3.12 and API supported 3.12–3.14.                    |
| `npm ls --depth=0 --workspace @iopsych/web`                                                       | Exit 0; existing installed web dependencies resolve, including Next 16.3.8, React 19.3.0, Vitest 5.0.2 and jsdom 30.1.1. This is not a clean-install test.                                                    |
| `.venv/bin/python --version`; `.venv/bin/python -m pip check`                                     | Python 3.12.16; no broken requirements. Existing environment reused.                                                                                                                                          |
| `docker info --format '{{.ServerVersion}}'`                                                       | Exit 0; Docker server 29.8.0 accessible. `command -v docker psql pg_isready` found Docker, not host PostgreSQL clients. No database/container mutations.                                                      |
| `npm exec --workspace @iopsych/web -- vitest run --coverage.enabled=false --cache=false`          | **104 tests passed, 23 files**, exit 0, 1.85 seconds. Coverage deliberately disabled; not the configured coverage gate.                                                                                       |
| `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest apps/api -o addopts='' -p no:cacheprovider` | **127 passed, 2 skipped**, exit 0, 3.97 seconds; PostgreSQL tests skipped without a PostgreSQL URL. One Starlette/httpx deprecation warning. Default coverage/strict addopts overridden; not `npm run check`. |

Saved setup `npm ci && PYTHON_BIN=python3.12 npm run api:install` is compatible
with inspected scripts and detected runtimes, but was **not rerun**: installed
dependencies already existed and this audit excludes dependency changes.
`scripts/install-api.sh` validates Python range, creates `.venv`, upgrades pip,
then installs requirements with eager upgrades; this is not a fully frozen
Python graph. Do not describe this audit as fresh-setup verification.

Runtime requirements for follow-up:

- Production web: `npm run build` then Next `start`, not `dev`. API: non-reload
  Uvicorn with the test-only application factory, database/session settings and
  shared Python/assets available. `scripts/run-api.sh` currently sources `.env`
  and uses `--reload`; `apps/api/.env.example:44` has an unquoted retention
  sentence. Static setup defect belongs to 6A; this audit did not execute
  arbitrary local configuration.
- Dedicated PostgreSQL 16 database and unique run schemas, migration privileges
  scoped to those schemas, seeded synthetic users from two organizations. For
  this audit the reserved names are web **3103**, API **8103**, database
  **iopsych_audit**; none was started. Preserve the existing container/database
  on 5432. Do not run root seed/migration commands against an inherited or
  existing application URL. `compose.yaml` uses a persistent named volume and
  `5432:5432`, so default `db:up` is not an isolated audit environment.
- `apps/api/tests/test_reports_postgres.py:postgres_report_factory` accepts
  `TEST_POSTGRES_URL` (preferred) or `DATABASE_URL`, creates a random schema,
  excludes `public` from search path, migrates/seeds and drops only that schema.
  It is a reusable isolation pattern, not populated-version coverage. A
  dedicated database must be provisioned explicitly before running it.
- Browser runner package/binaries and automated accessibility integration still
  need explicit setup. `package-lock.json` contains optional Playwright peer
  references and transitive `axe-core` via lint tooling; neither demonstrates an
  installed/configured browser test runner or runtime accessibility scan. No
  Playwright/Cypress configuration/spec suite was found.
- Controlled local mailbox and deterministic extraction must be injected through
  `apps/api/app/main.py:create_app` (`invitation_delivery`,
  `role_extraction_provider`, `session_factory`).
  `InvitationDeliveryAdapter.send` accepts `InvitationEmail`; module-level
  delivery is unconfigured and fails closed. Keep mailbox tokens
  process-local/ephemeral, out of logs, screenshots and committed artifacts. No
  paid/external provider is needed for deterministic tests.
- HTTPS/browser trust must be explicit. `scripts/security_smoke.py:172–174`
  forwards a Secure cookie manually using urllib; its dynamic ports (`309–310`)
  also do not honor this audit's reservation. Do not run it unchanged as a
  reserved-port browser check. Local HTTP smoke cannot prove staging HTTPS
  cookie or CSP hydration behavior.

Skipped checks: clean install, full lint/type/format/coverage gates, shared
TS/Python suites, build, actual launcher, database
migration/seed/verify/concurrency execution, production smoke, browser
scans/screenshots, manual accessibility, user research, fresh dependency/history
secret scans, hosted CI/branch protection and configured-provider smoke. These
are deliberate scope limits, not passes. No inability to access Docker is
claimed.

Historical evidence: `docs/security/evidence/verification.json` records
2026-09-30, base `038d275b5dedf7f2de987aed39180c00d6f3b362`, 420 tests/zero
skips and `hosted_github_run: false`. `finish.md` records 418 passes/two skips;
the final plan records 423 passes/two skips. Those different historical totals
are not current browser evidence and must not be combined with this audit's
targeted counts.

## 12A criterion-by-criterion map

All source/test references below are static unless included in the executed
suites above. Passing API tests generally use SQLite and ASGI transports;
passing web tests use mocked clients and jsdom, not a running service/browser.

| Criterion                                                                                              | Existing evidence                                                                                                                                                                                                                                                                 | Missing closure and owner                                                                                                                                                                                                  |
| ------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Production-build browser runner                                                                        | `apps/web/package.json` build/start; `apps/web/vitest.config.ts`; `scripts/security_smoke.py` starts production web/API over HTTP                                                                                                                                                 | No browser runner, browser binaries/configuration, trace/artifact policy or production browser CI. **12A runner owner**, scaffold eligible now.                                                                            |
| Isolated PostgreSQL data                                                                               | `test_reports_postgres.py:postgres_report_factory`; `.github/workflows/ci.yml` PostgreSQL 16 service                                                                                                                                                                              | Audit skipped both PG tests; runner needs dedicated DB + per-run isolation, fail-fast database guard, deterministic cleanup and zero required skips. **12A/database owner**.                                               |
| Controlled mailbox and deterministic extraction                                                        | `main.py:create_app`; `test_invitations.py:test_invite_consent_happy_path_is_private_hashed_and_audited`; `test_role_extraction.py:test_successful_extraction_creates_only_a_manager_approvable_draft`                                                                            | Inject local capture and deterministic provider into running test API; current unit fixtures are not production-path email/extraction evidence. **12A fixtures**, later **8A/11B** staging smoke.                          |
| Separate recruiter/manager/admin identities                                                            | `test_roles_api.py:test_profile_edits_create_versions_and_hiring_manager_approval_is_immutable`; `test_privacy.py:test_admin_export_and_anonymization_are_tenant_scoped_and_audited`                                                                                              | Browser contexts must log in separately, preserve database-authoritative RBAC, verify no session bleed. Provider login/provisioning awaits **7A/7B**; synthetic local-login coordination with **6A**.                      |
| Full role → extraction → revision → manager approval → invite → consent → completion → report → rights | Component screen tests listed below; `test_reports.py:test_report_persists_matching_snapshot_and_audits`; HTTP smoke starts from seeded approved profile/invite                                                                                                                   | No single browser journey. Missing invitation UI/delivery and review handoff prevent full path. **7C, 8A/8B, 9A–9C, 10A/10B**, then **12A**. Do not seed away the very transitions under test.                             |
| Decline, skips, reload/resume                                                                          | Candidate component tests at lines 183/225; invitation API decline test at 489                                                                                                                                                                                                    | Browser reload/current choices, storage getter denial, quota errors, stale incomplete edits, TTL, shared-device clearing and assigned-version resume missing. **9A/9B**, then **12A**.                                     |
| Expired/revoked/tampered invites; unapproved profiles; tenant/role negatives                           | `test_invitations.py` tests at 489, 527, 592; `test_reports.py:test_report_rejects_invalid_sources`; role CRUD/validation tests                                                                                                                                                   | Browser UI/route wiring, direct permalink and concurrent state changes still need real-browser cases, including archived roles. **12A**, feature dependencies **7C/8B**.                                                   |
| Provider failures, retry and idempotency                                                               | `test_invitations.py:test_delivery_and_missing_security_configuration_fail_closed`; extraction transient/invalid retry and audit rollback tests; PG concurrent submission/report test                                                                                             | No delivery uncertain-acceptance/commit-failure recovery or browser duplicate-click issuance proof; PG tests not run here. **8A**, then **12A**.                                                                           |
| Session expiry/sign-out                                                                                | `app/api/session/route.test.ts`; `report-workspace.test.tsx` generation retry/expired sign-in; privacy expired-session test                                                                                                                                                       | Visible sign-out, safe return path/provider callbacks and browser expiry/recovery await **7A**. Cookie/header unit checks do not establish browser enforcement.                                                            |
| Privacy cleanup and rights                                                                             | `privacy-workspace.test.tsx:125` export/confirmation; `test_privacy.py`; PG retention lock test                                                                                                                                                                                   | Actual downloaded JSON contents/MIME/name, rights after expiry, all lifecycle categories, draft/context and export/delete/generation races missing. **10A/10B/10C**, **12A**.                                              |
| Native dialogs/focus and privacy downloads                                                             | `report-detail.test.tsx:76` Escape/focus test; privacy test asserts data URI/download attribute                                                                                                                                                                                   | Dialog `showModal`/`close` are patched at test lines 16–34; no browser top-layer/inert background/Tab trap proof. Download attribute is not downloaded-file evidence. **12A/12B**.                                         |
| Real HTTPS cookies and CSP in staging                                                                  | `proxy.test.ts`, `internal-session.test.ts`, session/proxy route tests; HTTP smoke security assertions                                                                                                                                                                            | No HTTPS browser execution, hydration/console CSP checks, real cookie transport or cross-origin enforcement evidence. **11A/11B**, then **12A** staging lane.                                                              |
| Empty and populated migrations; version upgrades                                                       | `test_database_migrations.py:test_migration_upgrades_and_downgrades_empty_database`; `test_auth_migration_backfills_existing_user_subject` (populated SQLite user); PG empty-schema migrations; `test_reports.py:test_reports_preserve_approved_historical_versions_after_expiry` | Populated PostgreSQL old invitations, drafts, assessments and v1 reports across actual version/algorithm upgrade absent. Historical approved-profile test is not definition upgrade. **6C/9C** and **12A/database owner**. |
| Clean install/all checks/build/PG/smoke with zero required skips                                       | CI YAML schedules install/migrate/seed/verify/check/build/smoke                                                                                                                                                                                                                   | Audit targeted tests omit coverage and skip PG. Fresh revision-linked full gate and browser job required; no skipped required paths accepted as release completion. **12A + 6A/11A**.                                      |
| Fresh dependency and full-history secret scans                                                         | `.github/workflows/security.yml`: npm audit, pip-audit, pinned gitleaks; historical redacted artifacts                                                                                                                                                                            | No fresh audit scans or hosted results here. **Security/12A owner** reruns on integrated revision and retains redacted artifacts.                                                                                          |
| Hosted full journey/required negatives, revision/environment/results/limits, branch/release checks     | CI uploads check/build/smoke logs for 14 days; security uploads scans; historical verification JSON                                                                                                                                                                               | No hosted browser result, current release evidence manifest or branch-protection proof. Settings cannot be inferred from YAML. **Coordinator/release owner** with repository administration access, after implementation.  |
| Separate real configured-provider staging smoke                                                        | Mocked extraction tests, unconfigured delivery default                                                                                                                                                                                                                            | Not performed or authorized here; keep external-provider lane separate from deterministic CI and arrange controlled destination/usage through **8A/11B/11A** owners.                                                       |

## Ten-screen coverage inventory

Paths relative to `apps/web/app/`. References are precise test
descriptions/locations; all current component tests passed in this audit. Every
row still needs rendered browser accessibility scans, responsive inspection and
manual assistive-technology checks.

| Spec screen                       | Implementation / current test evidence                                                                                                                             | Gaps to exercise or implement                                                                                                                                                                                             |
| --------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1 Sign-in + organization switcher | `sign-in/sign-in-form.tsx`; adjacent tests at 31/55 establish session/rejected credential                                                                          | Token paste only, always redirects `/roles`; no org switcher/provider login/sign-out. Membership choice is **6B**, identity **7A/7B**. Test focus and announced errors.                                                   |
| 2 Roles list                      | `roles/roles-workspace.tsx`; tests at 105/119 cover manager empty state and load retry                                                                             | Browser authorization, long list/mobile layout, invitation visibility, session expiry; no ranking permitted.                                                                                                              |
| 3 Create role                     | Same workspace; test at 64 “supports keyboard-accessible recruiter role creation”                                                                                  | Real form validation/focus order, long JD/reflow and extraction progress transitions across running services.                                                                                                             |
| 4 Profile review                  | `roles/[roleId]/role-profile-workspace.tsx`; tests at 97/127/159 cover revision, extraction, manager approval                                                      | Real version navigation/radio keyboard operation; stale updates; request edits/reject/reason/handoff, metadata/archive controls (**7C**).                                                                                 |
| 5 Invite modal                    | No implemented invitation management screen/client path found; API tests exist                                                                                     | Entire screen and its error/loading/status/permission states await **8B**. No scan can close an absent screen.                                                                                                            |
| 6 Consent                         | `candidate/invites/[token]/candidate-assessment.tsx`; tests at 64/86/225: hidden questions, keyboard consent, decline                                              | Browser affirmative gate, expired/revoked pages, live-region announcements, comprehensible purpose/retention and working support contacts.                                                                                |
| 7 Assessment                      | Same component; tests at 86/183/252/275/356: six blocks, skip/resume, incomplete focus, retry/server acknowledgement, receipt write failure                        | Real keyboard/AT group labels and state changes; refresh/storage denial; device TTL; optional context/scope (**9A/9B**). Existing keyboard test explicitly focuses controls, so it does not prove full natural Tab order. |
| 8 Completion                      | Same component; tests at 337/356: server receipt and completion despite storage failure                                                                            | Rights link usability, no fit label, history/back/reload and answer-free receipt cleanup (**9A/10A**). No completion timing measurement.                                                                                  |
| 9 Recruiter report                | `reports/report-workspace.tsx` plus `reports/[reportId]/page.tsx`, `roles/[roleId]/reports/page.tsx`; workspace tests at 28/71/147; `report-detail.test.tsx:40,76` | Browser permalink/retry, native dialog/focus, reflow/contrast, actual item-level evidence (**9C**). Warning text is not proof users understand confidence or “worth discussing.”                                          |
| 10 Admin privacy                  | `privacy/privacy-workspace.tsx`; tests at 111/125/165/195/211: RBAC, export/delete, retention/errors, expiry and pagination                                        | Real downloads/confirmation focus and error recovery; UUID-only discovery gap (**10B**); lifecycle completeness (**10A/10C**).                                                                                            |

Also include home `/`, shared header/skip link, all
loading/empty/error/unavailable states, direct report links, and consent
decline/review states in scan coverage. `ui/site-header.test.tsx` covers hiding
internal navigation from candidate pages; `ui/workspace-states.test.tsx` covers
textual status/alerts. Route wrappers and static composition are explicitly
excluded from focused Vitest coverage, so coverage percentages cannot prove
every page works.

## 12B baseline checklist and findings

No item below is a WCAG conformance pass. This is the checklist to execute;
exact browser/OS/device/AT versions, viewport, reproduction steps, findings, fix
revision and retest results must be recorded by the follow-up owner. No accepted
limitations or user approvals have been invented.

| Criterion                                                | Static support / gap                                                                                                                                                                                                                               | Required evidence and ownership                                                                                                                                                                                                                         |
| -------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Automated accessibility on every screen                  | Semantic queries in jsdom; no browser axe integration found                                                                                                                                                                                        | **12B + runner owner** scan all ten screens and state variants; retain rule IDs, impacted nodes and remediation/retest. Missing invite screen remains blocked.                                                                                          |
| Keyboard-only completion                                 | Candidate keyboard test and native radio/button markup; some tests manually set focus                                                                                                                                                              | **12B** natural Tab/Shift-Tab/arrows/Enter/Space/Escape across entire journeys, no pointer assistance, no trap.                                                                                                                                         |
| Screen-reader announcements and semantic labels/headings | `aria-live` in profile/privacy workspaces; alerts, headings and input labels in components                                                                                                                                                         | **12B manual tester** names/roles/states, consent, choice groups, progress, validation and completion announcements with documented AT/browser pairing. No manual screen reader run occurred.                                                           |
| Focus order/visibility/return and native dialogs         | `report-detail.tsx` uses native dialog; component test patches it; candidate incomplete-block focus and shared skip link exist                                                                                                                     | **12B** verify initial focus, inert background, Escape, trigger restoration, route transitions, error focus, focus not obscured (WCAG 2.2) on actual browsers.                                                                                          |
| Contrast and non-color cues                              | `ui/status-badge.tsx`, textual report labels; theme/classes in `globals.css`                                                                                                                                                                       | **12B** measure rendered text/non-text contrast for normal, focus, disabled/error/uncertainty states. Tailwind class names alone do not establish ratios.                                                                                               |
| Zoom/reflow and mobile                                   | Responsive grid/classes and break-words; no viewport evidence                                                                                                                                                                                      | **12B** 200% text zoom, 400%/320 CSS-pixel reflow, long content, portrait/landscape; inspect clipping/overlap/horizontal scroll, dialogs and assessment choices.                                                                                        |
| Reduced motion                                           | `globals.css` reduces animation/transition duration and shimmer iteration                                                                                                                                                                          | **12B** browser emulate reduced motion, verify computed behavior/loading still perceivable; CSS presence is not executed proof.                                                                                                                         |
| Touch targets                                            | Many buttons use `min-h-11`/`min-h-12`; assessment radios use `size-5`                                                                                                                                                                             | **12B** measure effective clickable areas/spacing, including labels, links, dialog close and adjacent most/least controls; do not infer failure from radio size alone.                                                                                  |
| Copy, recovery and support                               | Report warning says “worth discussing” is not “not qualified”; shared retry states exist                                                                                                                                                           | Candidate unavailable branch at `candidate-assessment.tsx:383` has message but no retry/help action. Fix **9A**; confirm privacy/accommodation contacts with **12C**, then **12B** comprehension/recovery checks.                                       |
| Honest persistence/status                                | `candidate-assessment.tsx:172,176` reads storage getter before helper catch; save effect at 230 catches writes; saved label at 673 derives from choices; `candidate-storage.ts:completeCandidateAssessment` stores full `response_set` without TTL | Static confirmed implementation gaps, not reproduced browser incidents: **9A** handle getter denial, truthful saved status, stale/empty draft edits, minimal receipts/expiry. Existing receipt-write failure test does not cover initial getter denial. |
| Under-ten-minute median completion                       | UI timing expectation/copy is not a measurement                                                                                                                                                                                                    | **Product research/12B** intended users with synthetic tasks; document sample, start/end definition, individual durations/median, interruptions/skips and limitations. Target median <10 minutes; no measured result exists here.                       |
| Consent comprehension                                    | Text present and affirmative-gate tests                                                                                                                                                                                                            | **Product research + privacy owner** assess purpose, data use, retention, voluntary decline, rights and support using predefined questions; no invented pass threshold or approval.                                                                     |
| Confidence/evidence and “worth discussing” comprehension | Report warning and fixture labels tested; structure policy conflict remains in spec sections 5/7                                                                                                                                                   | **Product/I-O decision owner 6B**, **9C**, then **research/12B** test manager/recruiter interpretation. Do not change formula or claim calibrated confidence/scientific validation.                                                                     |
| Blocking fixes and accepted limitations                  | No complete accessibility issue register or baseline evidence found                                                                                                                                                                                | **12B lead** severity/owner/affected screens, fix+retest evidence and explicitly accountable acceptance of remaining limits; cannot close while required screens or studies are absent.                                                                 |

Suggested manual coverage includes Chromium and Firefox plus WebKit/Safari for
native dialogs/downloads, a documented desktop screen-reader pairing, and actual
mobile/touch verification. These are proposed coverage targets, not an executed
device matrix or agreed product decision. User research must involve intended
users; automated agents do not substitute for them.

## Prioritized independent follow-up ownership

| Priority / package                           | Owned files and boundary                                                                                                                                                                                                 | Eligibility / acceptance                                                                                                                                                                                                                                                               |
| -------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| P0 — 12A runner scaffold                     | Proposed new `e2e/` runner config, lifecycle/fixtures and initial browser specs; dedicated workflow after integration. Dependency manifest/lock changes require coordination with 6A; no shared schema/migration needed. | **Eligible now.** Build/start production services, fail if ports/database mismatch or required dependencies unavailable, isolate schemas, retain sanitized revision-tagged results, exercise public health/rendering and a limited authenticated path. Call it scaffold, not full 12A. |
| P0 — 6A setup owner                          | Root package/setup/start scripts, runtime docs and synthetic local-login                                                                                                                                                 | Already allocated by coordinator. Runner consumes the resulting login interface; do not independently add competing auth or root scripts.                                                                                                                                              |
| P0 — 12A deterministic fixtures owner        | Test-only factory/helpers under new E2E tree using existing `create_app` injection; mailbox/extractor fixtures                                                                                                           | Eligible now with explicit runner runtime parameters. Coordinate with 8A before lifecycle contracts change. Never expose test control endpoints in production or persist raw bearer tokens in artifacts.                                                                               |
| P1 — 12B incremental audit owner             | New issue/evidence docs and browser accessibility cases on existing screens                                                                                                                                              | Eligible after minimal runner; can inspect existing screens now. Record missing screens as blocked, not excluded. Application fixes dispatched separately to feature owners.                                                                                                           |
| P1 — 6C + database test owner                | Future populated PostgreSQL upgrade scenarios; no migration edits authorized by this report                                                                                                                              | Prepare synthetic prior-state scenario design now; implement after approved assignment/report compatibility contracts. Coordinate all shared contracts/migrations through Orca ask.                                                                                                    |
| P1 — 7–10 feature owners                     | Login/accounts/review, invitation UI/delivery, storage/context/report evidence, complete rights/discovery                                                                                                                | Full browser journey depends on these packages and 6B decisions; tests must follow implemented contracts and approved scope.                                                                                                                                                           |
| P2 — 11A/11B + release/security owner        | Staging production/TLS lanes, provider smoke, fresh scans, required checks and evidence manifest                                                                                                                         | Requires chosen topology/configuration and explicit staging authorization. No hosted result or branch protection may be asserted from local workflow YAML.                                                                                                                             |
| P2 — 12B research/manual tester + 12C owners | Browser/device/AT log, user-study timing/comprehension results, actual contact and review approvals                                                                                                                      | Requires completed screens and intended users/accountable reviewers. Engineering cannot self-approve interpretation, privacy or real-candidate use.                                                                                                                                    |

Next eligible package: **12A runner scaffolding**, with independent test-only
fixture work and incremental 12B checklist preparation. Full 12A acceptance
remains dependent on packages 7–10 and 11A/11B; full 12B depends on completed
screens, runner and manual/user evidence. No blockers prevent delivering this
audit; these dependencies block release-package closure.

## Handoff

Only changed file: `docs/implementation/12ab-audit.md`. No migrations, contracts
or dependencies changed; no shared-contract approval was necessary. Coordinator
received an early runner-scaffold recommendation through Orca. This document
records commands/results and skipped checks above; commit identifier is supplied
in the worker completion message so the document need not embed its own commit
hash.
