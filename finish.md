# IOPsych: remaining work before release

Reviewed October 11, 2026. This is a code-and-documentation readiness review,
not a record of a deployed release. Tasks below are ordered by dependency and
release importance. Each task includes a concrete completion condition; passing
existing tests alone does not close it.

## Release assessment

**The project has a substantial functional core, but it is not yet a
self-service, deployable product.** The largest gaps are production identity
integration, working invitation delivery and management, complete browser
end-to-end coverage, and deployment/operations. There are also specific setup,
browser persistence, privacy, and versioning defects to address.

Two release targets should be kept separate:

- **Hosted portfolio/synthetic demo:** complete the technical workflow, deploy
  it reproducibly, and demonstrate it with synthetic data. This can be a strong
  résumé project without claiming that the instrument is scientifically
  validated.
- **Real candidate pilot:** additionaally requires reviewed assessment content,
  approved interpretation and privacy policies, operational privacy controls,
  accommodation support, and accountable pilot owners. The specification
  explicitly requires synthetic data until the relevant reviews are complete.

The current implementation is close to the end of specification packages 0–4,
with important seams still missing. Packages **5A (complete E2E), 5B
(accessibility/UX), and 5C (pilot operations)** remain unfinished. Earlier
packages should not be marked complete merely because their adapter interfaces
or unit tests exist.

## What already works

Preserve these capabilities rather than rebuilding them:

- Next.js/FastAPI monorepo, shared Zod/Pydantic/JSON Schema contracts,
  reproducible scripts, and seven Alembic migrations.
- Database-backed tenant/RBAC enforcement and HTTP-only internal session
  cookies, same-origin mutation checks, CSP nonces, response hardening, and
  credential redaction.
- Role creation, structured extraction adapter, source-evidence validation,
  immutable profile revisions, version history, and hiring-manager-only
  approval.
- Signed invitations with hashes at rest, expiry/revocation, consent/decline,
  six assessment blocks, skips, deterministic scoring, and idempotent server
  submission.
- Persisted reports with approved input versions, deterministic interview
  prompts, confidence, evidence drawers, and no aggregate hiring score or
  ranking.
- Administrator export/anonymization, audit lookup, a bounded retention command,
  and database audit immutability triggers.
- Existing component, contract, API, migration, and PostgreSQL concurrency
  tests; CI and security workflows; a production HTTP smoke script.

Some of these work only through tests, injected adapters, or direct API calls.
That distinction is central to the remaining plan.

## Review evidence and limits

Reviewed the root product/specification/research documents, app/package READMEs,
security threat model and verification documentation, workflows, environment
templates, migrations, shared domain modules, API services/routes, browser
workspaces/proxies/storage, setup/smoke scripts, and test coverage. `notes.md` is exploratory conversation and `test.md` contains greeting text; neither is an acceptance test plan. Treat
`mvp-spec.md` as the product authority where older ideas conflict with it.

Checks run against the existing local installations during this review:

| Verification                                                | Result                | Qualification                                                                                       |
| ----------------------------------------------------------- | --------------------- | --------------------------------------------------------------------------------------------------- |
| `npm run check`                                             | Passed                | Formatting, ESLint/Ruff, TypeScript/mypy, and configured test/coverage gates passed.                |
| Web tests                                                   | 99 passed             | 22 test files; component/route tests, not real browser coverage.                                    |
| Shared TypeScript tests                                     | 99 passed             | 3 test files.                                                                                       |
| Shared Python tests                                         | 93 passed             | Contract/domain tests.                                                                              |
| API tests                                                   | 127 passed, 2 skipped | 100% configured application coverage; PostgreSQL tests skipped without a configured test database.  |
| `npm run build`                                             | Passed                | Shared package and production Next.js build completed.                                              |
| Source the supplied API environment template with Bash      | **Failed, exit 127**  | `.env.example` line 44 produces `data: command not found`; see task 1.                              |
| Fresh PostgreSQL migration/concurrency and production smoke | Not run               | No test PostgreSQL URL was supplied; Docker socket access was denied in this execution environment. |
| Fresh dependency/secret scans and hosted CI/deployment      | Not verified          | September 30 evidence is historical, not proof of the October 11 dependency or deployed state.      |

Total executed tests: **418 passed, 2 skipped**. The prior documented clean
Linux verification reports 420 passed with zero skips. Do not conflate the two
runs. Local check/build logs for this review are in
`/tmp/iopsych-review-check.log` and `/tmp/iopsych-review-build.log`; these
temporary files are not durable release evidence.

Labels below distinguish **confirmed defect**, **missing implementation**,
**design decision**, and **verification/operations gap**. Suspected failure
scenarios are identified as such rather than presented as reproduced production
incidents.

## Ordered completion plan

### 1. Fi x the documented first-run environment loading — P0, confirmed defect

**Evidence:** [API environment template](apps/api/.env.example),
[API launcher](scripts/run-api.sh), [setup instructions](README.md).

The README instructs copying the template to `apps/api/.env`. The launcher then
sources that file as shell code.
`INVITE_RETENTION_STATEMENT=Pilot data is retained ...` is unquoted, so Bash
attempts to execute `data` and the launcher exits under `set -e`. The advertised
first-run path therefore fails even though the build/test gates pass.

- [ ] Quote the template's free-text values and preferably replace shell
      sourcing with a dotenv-aware startup path. Preserve the API host/port
      configuration behavior and avoid executing configuration as shell code.
- [ ] Make clean setup use the committed JavaScript lockfile (`npm ci` where
      appropriate); document the supported runtimes and exact start commands.
- [ ] Add a setup/startup regression that uses the example configuration and
      does not require genuine provider credentials.

**Done when:** a fresh clone following only the README starts both applications
and reaches their health endpoints. Test the actual launcher, not just dotenv
parsing.

### 2. Resolve the contradictory structure comparison policy — P0, design/correctness blocker

**Evidence:** `mvp-spec.md` sections 5 and 7;
[construct metadata](packages/shared/src/constructs.ts);
[TypeScript matcher](packages/shared/src/matching.ts);
[Python matcher](packages/shared/python/iopsych_contracts/matching.py).

The implementation follows the spec's explicit inverse formula. However, the
spec also says high role structure satisfies high candidate preference for
structure. Under the implemented formula, role structure **5** and candidate
structure preference **5** compare as `abs((6 - 5) - 5) = 4`, producing
potential friction; role **1**, candidate **5** produces alignment. These
examples conflict with the behavioral definitions. Existing boundary tests
verify the formula, not the intended meaning.

- [ ] Record one approved interpretation with the product/I-O reviewer: either
      compare structure availability directly to preference, or redefine the
      role quantity so inversion has the intended meaning.
- [ ] Align the spec, extraction instructions, labels, definitions, both
      matchers, schemas, fixtures, and report explanations with that decision.
- [ ] Add meaning-based examples for low/high structure and low/high preference,
      plus cross-language parity cases.
- [ ] If matching behavior changes, publish a new algorithm version and preserve
      old report interpretation; complete task 7 before deploying the change
      over existing data.

**Done when:** a reviewer can explain the four extreme cases in plain language
and both implementations produce the approved outcomes. Do not silently change
historical reports.

### 3. Replace token-paste sign-in with an actual identity workflow — P0, missing implementation

**Evidence:** [sign-in form](apps/web/app/sign-in/sign-in-form.tsx),
[session route](apps/web/app/api/session/route.ts),
[JWT verifier](apps/api/app/auth/tokens.py),
[user model](apps/api/app/database/models.py),
[header](apps/web/app/ui/site-header.tsx).

Current sign-in requires an internal user to supply a JWT manually. The API
verifies HS256 tokens, but there is no provider login/callback, user
provisioning, or administrator account-management workflow. Users currently
belong to one organization and have a globally unique `auth_subject`; a
multi-organization switcher cannot simply be added to that model. The sign-out
endpoint exists but there is no visible sign-out action. Report links supply
`returnTo`, but successful sign-in always redirects to `/roles`.

- [ ] Integrate a vetted identity provider and its actual claim/signature
      verification contract. Keep database-authoritative permissions and tenant
      isolation.
- [ ] Provide a documented, controlled way to provision the pilot organization,
      administrator, recruiter, and manager; deactivate users and change
      permissions. Add explicit active/disabled state if using that policy.
- [ ] Add account/organization context, visible sign-out, expired-session
      recovery, and safe local-path `returnTo` handling.
- [ ] Decide whether the first pilot intentionally supports one organization per
      user. Document that limit or implement memberships and a tested tenant
      switcher.
- [ ] Test callback/session failures, revoked/disabled users, role changes,
      token expiry, tenant switching if supported, and open-redirect prevention.

**Done when:** a nontechnical recruiter and manager can independently sign in
and complete their permitted tasks without generating tokens or asking an
engineer to edit the database.

### 4. Implement production invitation delivery and reliable issuance — P0, missing implementation/reliability risk

**Evidence:** [delivery interface](apps/api/app/invitations/delivery.py),
[app factory](apps/api/app/main.py),
[invitation service](apps/api/app/invitations/service.py).

The module-level application always defaults to
`UnconfiguredInvitationDelivery`, which rejects sending. There is no
environment-configured production email adapter. In addition, the service sends
email before the request's database/audit transaction commits. A provider
success followed by commit failure can deliver a link whose database record
never exists; retries can send additional invitations. This is a code-derived
failure scenario, not a reproduced provider incident.

- [ ] Implement and configure a transactional delivery adapter with verified
      sender identity, timeouts, safe errors, and delivery credentials in a
      secret store.
- [ ] Define issuance idempotency and recovery for uncertain provider outcomes
      and database failures. Use a durable delivery design or an explicitly
      documented minimal retry strategy.
- [ ] Keep raw invite tokens out of database records, ordinary logs, audit
      metadata, and API responses. If a queue needs delivery credentials,
      explicitly design its encryption, access, expiry, and deletion policy
      rather than persisting plaintext tokens in an outbox.
- [ ] Handle failed delivery, reissue/resend, revocation, bounces, and provider
      webhook authentication/deduplication where used. Reissuing must make the
      old link's status clear.
- [ ] Test provider failure, timeout after acceptance, duplicate requests, and
      commit/audit failure after provider acceptance.

**Done when:** an invite created in staging reaches a controlled mailbox, opens
a valid candidate page, and failures have a recoverable state without token
disclosure or uncontrolled duplicate email.

### 5. Complete recruiter invitation management — P0, missing implementation

**Evidence:** [invitation API](apps/api/app/invitations/router.py),
[internal proxy allowlist](apps/web/app/api/internal/[...path]/route.ts),
[profile workspace](apps/web/app/roles/[roleId]/role-profile-workspace.tsx),
[API client](apps/web/lib/api-client.ts).

The API can create/revoke invitations, but the internal browser proxy does not
allow either route, the client has no corresponding functions, and the UI has no
invite form. There is also no invite-list endpoint for pending, declined,
expired, or revoked invitations; report discovery only lists submitted
assessments.

- [ ] Add shared invitation contracts, proxy routes, client methods, and an
      accessible invite form/modal with email, approved version, expiry, purpose
      notice, and preview.
- [ ] Add a tenant-scoped, bounded invitation list with
      delivery/consent/submission status and appropriate revoke/reissue actions.
- [ ] Disable creation for unapproved/archived roles and show actionable
      provider/configuration errors.
- [ ] Test manager/recruiter/admin permissions, cross-tenant identifiers,
      duplicate clicks, expiry validation, and the browser-to-API route wiring.

**Done when:** the spec's core journey—create role → manager approval → email
invitation—works entirely in the browser.

### 6. Fix candidate browser persistence and recovery — P1, confirmed code defects

**Evidence:**
[candidate workspace](apps/web/app/candidate/invites/[token]/candidate-assessment.tsx),
[browser storage](apps/web/lib/candidate-storage.ts).

- [ ] Handle a throwing `window.localStorage` getter. The initial load evaluates
      `window.localStorage` before entering the helpers' `try` blocks, so a
      storage access exception becomes an invitation error despite a valid
      consented link. Allow an in-memory journey when storage is unavailable.
- [ ] Show “Saved on this device” only after a successful write. Current display
      logic uses the presence of responses, while storage write failures are
      swallowed, so candidates can be told their progress is saved when it is
      not.
- [ ] Remove raw answers from the completion receipt and expire/clear browser
      drafts and legacy completion snapshots. Current completion storage
      includes the full `response_set` with no TTL; server anonymization cannot
      erase it from an offline device.
- [ ] Prevent stale saved answers from reappearing when a previously complete
      choice becomes incomplete. Persistence omits incomplete blocks and skips
      writes entirely for an empty response set, leaving the old saved snapshot
      in that case.
- [ ] Add an explicit save/exit or clear-device-data action, explain
      shared-device behavior, and provide retry/help on an unavailable
      invitation page.
- [ ] Test denied storage access, quota failures, refresh/resume, stale draft
      cleanup, server-confirmed completion, expiry/revocation, and changing a
      completed answer to an incomplete one.

**Done when:** the candidate can finish with storage disabled, save claims
reflect actual persistence, and the browser does not retain completed answers
indefinitely.

### 7. Pin assessment versions and preserve historical report readers — P1, missing lifecycle support

**Evidence:** [invitation/assessment models](apps/api/app/database/models.py),
`PILOT_DEFINITION_PATH` and `submit()` in the invitation service, the candidate
workspace's hardcoded `PILOT_ASSESSMENT_DEFINITION_V1`, and `MatchingResult`
schemas in both languages.

Submission snapshots are versioned, but an invitation does not pin an assessment
definition at issuance. Both browser and server use the current checked-in pilot
definition. Updating it can strand in-progress candidates or change what an
outstanding invitation asks them to complete. Matching readers also accept only
literal version `1.0.0`; simply changing that literal on a new release can make
old stored reports unreadable.

- [ ] Bind each invitation to an immutable assessment definition/scoring version
      and serve that version after consent; retain definitions needed by
      outstanding invitations and historical records.
- [ ] Reject new assignments of unreviewed/retired definitions in real-pilot
      mode while retaining historical read/scoring compatibility. The current
      pilot definition is explicitly `draft` and is nevertheless rendered and
      scored.
- [ ] Add version-aware report readers and an algorithm registry/dispatch
      policy. A new algorithm must not reinterpret old persisted output.
- [ ] Test an upgrade with an outstanding invitation, saved draft, submitted
      assessment, and v1 report already present.

**Done when:** deploying a new assessment or algorithm leaves old invitations
usable under their assigned policy and old reports readable exactly as saved.

### 8. Complete item-level explainability — P1, requirement gap

**Evidence:** [report service](apps/api/app/reports/service.py),
[matching contracts](packages/shared/src/matching.ts),
[report evidence UI](apps/web/app/reports/report-detail.tsx); FR-07 and the
spec's success criteria.

Reports include role excerpts and candidate aggregate counts/raw scores, but the
candidate summary does not expose the specific contributing item IDs,
statements, or most/least/skip choices. The inputs are stored server-side, yet
recruiters cannot inspect that chain from the evidence drawer.

- [ ] Include the exact versioned item/block references and relevant choices
      contributing to each construct, with appropriately limited internal
      access.
- [ ] Explain how those choices produce the raw score, rating threshold,
      confidence, comparison, and question selection.
- [ ] Use approved behavioral wording and distinguish evidence-completeness
      “confidence” from a scientifically calibrated probability. Do not imply
      that answering every item validates the instrument.
- [ ] Test traceability with complete, skipped, low-confidence, and historical
      assessments.

**Done when:** every displayed signal can be traced from its evidence drawer to
exact role evidence and assessment items, not just aggregate counts.

### 9. Finish the remaining specified product journeys — P1, missing implementation/scope decisions

**Evidence:** `mvp-spec.md` sections 3, 10, and 11; role/profile routes and
schemas; candidate assessment contracts; role and privacy workspaces.

- [ ] Provide the manager handoff and request-edits/reject flow, with reason,
      status, attribution, and audit events. Current states are only
      draft/approved/superseded; drafts can be edited but there is no explicit
      submission/review decision workflow.
- [ ] Decide and document server-backed draft progress. The specified
      `/responses` route is absent; current save/resume is device-only.
      Implement consent-gated server persistence if cross-device resume is
      required, or explicitly revise the MVP promise and acceptance criteria to
      device-only behavior.
- [ ] Implement optional candidate context and its retention/export/deletion
      behavior, or explicitly remove it from the MVP scope. Current assessment
      payloads have no context field.
- [ ] Provide a separate interview-notes workflow if it remains in scope, or
      explicitly document where notes are kept externally. Never mix
      notes/dispositions into immutable system-derived reports.
- [ ] Expose role metadata editing and archival in the browser, or document
      their intentional omission; API endpoints already exist but the
      client/workspace lacks those controls.
- [ ] Complete practical administrator discovery: locate records by permitted
      candidate/role/invite references rather than requiring an assessment UUID
      for every request. Audit lookup by assessment UUID currently filters only
      that exact entity and does not automatically include related invite,
      consent, and report events.

**Done when:** each required journey is either implemented and tested or covered
by a deliberate, recorded MVP scope revision. Avoid silently treating missing
screens as completed backend features.

### 10. Close privacy lifecycle gaps — P1, required before real candidate data

**Evidence:** [privacy service](apps/api/app/privacy/service.py),
[consent model](apps/api/app/database/models.py),
[candidate consent response](apps/api/app/invitations/service.py),
[retention scheduler](apps/api/app/privacy/retention.py).

- [ ] Cover expired/unopened, declined, revoked, and consented-but-unsubmitted
      invitations. Current cleanup selects submitted `Assessment` records only,
      and export/delete is assessment-ID-based; invitation email/consent can
      remain indefinitely when no assessment exists.
- [ ] Freeze the notice content and applicable retention policy at
      consent/assignment, not just the notice-version string. Current landing
      copy comes from live settings, while the actual deadline is created using
      settings at submission. Configuration changes can make the
      displayed/previously accepted policy diverge.
- [ ] Provide a workable identity-verification and correction process, including
      what happens after link expiry. The existing mailto contact is a
      legitimate manual starting point, but no operational procedure is
      documented; immutable submissions currently reject changed answers.
- [ ] Define consent withdrawal separately from initial decline and specify
      whether it revokes access, deletes data, and invalidates derived reports.
      Initial consent is terminal today.
- [ ] Schedule the existing cleanup command, handle backlogs larger than one
      batch, and alert on missed runs and overdue records. Document how backup
      restores reapply deletion tombstones.
- [ ] Test deletion/export/generation concurrency and full lifecycle cleanup on
      PostgreSQL; preserve necessary non-identifying audit history under the
      approved policy.

**Done when:** every category of candidate data has an enforced deadline and
rights workflow, and an unattended scheduled rehearsal removes due data and
reports while preserving the intended audit record.

### 11. Harden configuration, readiness, and request resource limits — P1, deployment gap

**Evidence:** [application factory](apps/api/app/main.py),
[security middleware](apps/api/app/security.py),
[proxy routes](apps/web/app/api),
[extraction settings/service](apps/api/app/extraction), environment templates,
and the accepted limits in the threat model.

- [ ] Add explicit deployment-mode validation: reject public sample signing
      keys, invalid contact addresses, loopback upstreams/candidate URLs in
      hosted mode, and required providers that are not configured.
- [ ] Keep liveness separate from readiness. `/health` intentionally returns
      success without checking database connectivity, migration level, or
      required configuration; that is insufficient as the sole deployment gate.
      Do not call paid providers on every probe.
- [ ] Bound request body size and upstream timeouts at ingress and proxy
      boundaries. The browser proxies buffer entire bodies/responses and their
      `fetch` calls have no explicit abort deadline.
- [ ] Configure shared ingress rate limits and restrict direct API access.
      Existing counters are process-local, and candidate requests through Next
      share an API peer/IP budget; signed-token limits do not provide
      independent per-browser ingress protection.
- [ ] Review synchronous database work in async routes/middleware under slow
      queries and locks. Invitation creation also invokes a synchronous delivery
      adapter inside an async endpoint. Offload blocking work coherently or
      adopt an async stack, preserving request transactions and audits.
- [ ] Bound extraction cost/concurrency, total retry duration, output size, and
      duplicate extraction requests. Its default three 30-second attempts can
      exceed a hosting request timeout. Verify an actual configured-provider
      request in staging with synthetic job text; mocked adapter tests are not
      live-provider evidence.

**Done when:** bad production configuration fails before traffic is admitted;
oversized, stalled, and burst requests remain bounded; and a slow dependency
does not stall unrelated users.

### 12. Add reproducible staging and production deployment — P0 for deployability

**Evidence:** [Compose file](compose.yaml), package scripts, setup scripts, CI
workflows, README. Compose provisions local PostgreSQL only; no API/web
deployment packaging, release workflow, or deployment runbook is present.

- [ ] Choose and record the hosting topology, public web origin, private API
      connectivity, managed PostgreSQL, and deployment region. Keep the initial
      topology simple and appropriate for the pilot.
- [ ] Add deployable API packaging/startup and the necessary web hosting
      configuration. If containerizing, use production commands without
      `--reload`, appropriate process lifecycle/graceful shutdown, and
      constrained runtime privileges.
- [ ] Package the shared Python library and checked-in definition files. API
      code reads assets by monorepo-relative filesystem paths; an image
      containing only `apps/api` will omit required files.
- [ ] Provision staging separately from production, TLS/redirects, secret
      injection, database/backup encryption, restricted networking, and explicit
      application versus migration database privileges. Audit triggers are not a
      substitute for restricting a table-owner/superuser account.
- [ ] Run migrations once as a controlled release step, validate schema
      compatibility, and document rollback or forward-fix behavior for data
      migrations. Never seed synthetic demo organizations into a real pilot
      database by default.
- [ ] Add preview/staging deployment from CI, post-deploy readiness/smoke gates,
      immutable release identifiers, and a tested rollback path.
- [ ] Bind local PostgreSQL to loopback by default; the current `5432:5432`
      mapping exposes it on host interfaces with development credentials.

**Done when:** a clean checkout can deploy a protected staging instance using
documented configuration, pass readiness and synthetic workflow checks, and roll
back without losing or misinterpreting data.

### 13. Add observability, backups, and support runbooks — P1, operations gap

**Evidence:** `mvp-spec.md` sections 8, 12, and 15; existing log redaction;
security threat model. No monitoring/backup/deployment runbooks or metrics
implementation were found.

- [ ] Add structured, allowlisted operational logs, correlation IDs, safe
      exception/error tracking, and release identifiers. Generic 500 responses
      should remain safe while operators receive useful diagnostics.
- [ ] Configure web/ingress/email-provider/telemetry redaction as well as Python
      logging. Do not record candidate token paths, Authorization, cookies,
      response bodies, PII, exports, or exception locals containing credentials.
- [ ] Monitor availability, API/report/extraction latency and failures, delivery
      errors, database pressure, rate limiting, and retention backlog; add
      actionable alerts and a named responder.
- [ ] Track the spec's operational/usability metrics with minimal data:
      extraction success/edit rate, time to approval, completion time/skip rate,
      insufficient-evidence frequency, report errors, and user
      clarity/usefulness. Do not introduce candidate ranking or hiring-outcome
      optimization.
- [ ] Enable managed backups and perform a restore drill. Record
      recovery-time/data-loss objectives, credentials, deletion replay, and
      restoration verification.
- [ ] Write deployment, rollback, incident response, signing-key rotation,
      support, accommodation, and data-rights runbooks. Define what rotation
      does to outstanding sessions/invitations.

**Done when:** a rehearsed failure produces a useful alert, an operator can
diagnose it without sensitive payloads, and backup recovery plus deletion replay
is demonstrated.

### 14. Complete package 5A with real browser and PostgreSQL E2E tests — P1, verification gap

**Evidence:** current Vitest/jsdom tests;
[production smoke script](scripts/security_smoke.py);
[CI](.github/workflows/ci.yml);
[PostgreSQL regression](apps/api/tests/test_reports_postgres.py).

The production smoke is valuable, but it directly seeds an approved role and
candidate invitation and uses synthetic JWTs. It does not exercise browser
interaction, real account login, recruiter creation/extraction/approval, or
email delivery. It also explicitly forwards Secure cookies over loopback HTTP
rather than relying on browser cookie enforcement.

- [ ] Add a browser E2E runner against production builds, a disposable
      PostgreSQL schema/database, controlled email capture, and deterministic
      extraction responses.
- [ ] Cover recruiter login/create/extract/revise → separate manager
      login/approval → recruiter invite → candidate consent/complete → recruiter
      generate/read report → admin export/delete.
- [ ] Cover decline, skips, reload/resume, expired/revoked links, unapproved
      profiles, tenant isolation, role restrictions, provider failures,
      retry/idempotency, session expiry/sign-out, privacy cleanup, and
      historical-version upgrades.
- [ ] Verify native dialogs/focus, CSP hydration, downloadable privacy exports,
      and actual Secure-cookie behavior in an HTTPS staging browser.
- [ ] Re-run all existing checks, clean-install build, PostgreSQL
      migrations/seed/verify/concurrency tests, and production smoke with **zero
      required skips**. Test migration upgrades over populated prior-version
      data as well as an empty database.
- [ ] Run dependency and full-history secret scans again; obtain actual hosted
      workflow results and retain revision-tagged evidence. Configure required
      CI/security checks and branch protection for releases.

**Done when:** hosted CI reliably verifies the entire browser journey and
required negative paths, with fresh release evidence tied to the exact deployed
revision.

### 15. Complete package 5B: accessibility and usability evidence — P1, verification gap

**Evidence:** existing semantic labels, focus code, keyboard-oriented component
tests, and spec WCAG 2.2 AA/usability acceptance criteria. No complete
accessibility or user-study report was found.

- [ ] Run automated browser accessibility checks across sign-in, roles, profile
      review, invitations, consent, assessment, reports/dialogs, and privacy
      administration.
- [ ] Manually test keyboard-only completion, screen-reader announcements, focus
      order/return, errors, zoom/reflow, mobile layouts, contrast, touch
      targets, and reduced motion. jsdom assertions do not establish
      real-browser accessibility.
- [ ] Test with intended users: measure median completion time under ten
      minutes, consent comprehension, manager understanding of
      confidence/evidence, and recruiter understanding that “worth discussing”
      does not mean “not qualified.”
- [ ] Improve unavailable/empty/error states with useful recovery and support
      links; replace placeholder privacy/accommodation contacts with working
      addresses.
- [ ] Document devices/browsers, findings, fixes, and remaining accepted
      limitations.

**Done when:** critical journeys pass manual and automated checks and the spec's
comprehension/timing targets have measured evidence.

### 16. Complete package 5C and obtain real-pilot approval — required before real candidate use

**Evidence:** unchecked launch checklist and owner/review requirements in
`mvp-spec.md`; draft assessment definition; interview-library `review_status`
values; example contacts in configuration.

- [ ] Name the product/engineering owners, qualified I-O reviewer, privacy/legal
      reviewer, and support/accommodation contacts; choose the pilot
      organization and role family.
- [ ] Record actual review of constructs, forced-choice statements, thresholds,
      confidence interpretation, matching semantics, and interview prompts. A
      JSON field saying `approved` is not evidence of external content review.
- [ ] Approve purpose, consent/withdrawal, retention, privacy notice, rights
      verification/correction, and accommodations procedures for the intended
      pilot. Obtain jurisdiction-specific guidance from the accountable reviewer
      rather than assuming the product warning settles those questions.
- [ ] Train recruiters/managers on limits and neutral questioning. State clearly
      that the instrument is a usability pilot and is not validated to predict
      performance or determine hiring outcomes.
- [ ] Run a full synthetic staging rehearsal, verify
      email/support/rights/cleanup/rollback, and record the spec's release
      checklist with evidence and owner sign-off.
- [ ] If authorized for real participants, begin with the specified small pilot
      and monitor operational/user-experience issues. Define stop/rollback
      criteria and review outcomes before expansion.

**Done when:** accountable owners sign off on evidence, users have working
support paths, and the synthetic rehearsal passes. A hosted portfolio demo may
remain synthetic while these approvals are pending.

### 17. Make the finished project credible on a résumé — portfolio priority

- [ ] Publish a stable synthetic demo with controlled recruiter/manager/admin
      access and a reset policy. Do not expose reusable signing keys or let
      anonymous visitors email arbitrary addresses/use unlimited extraction
      credits.
- [ ] Add a short README demo walkthrough, screenshots or a brief video covering
      role approval through report evidence, a system architecture diagram, and
      a link to the deployed demo.
- [ ] Write concise engineering decision records for tenant authorization,
      immutable profiles/reports/audit, consent/token handling, deterministic
      matching, LLM validation, and deployment tradeoffs.
- [ ] Publish measured performance/reliability results with workload,
      environment, revision, and limitations. Cite actual CI/browser/restore
      evidence; do not claim production scale or scientific validity from unit
      coverage.
- [ ] Add a clear license, contribution/setup guidance, release notes, and an
      honest known-limitations page.
- [ ] Label older exploratory documents as historical, remove greeting/test
      clutter intentionally, and separate unrelated CUDA/inference learning
      material from the product narrative. Existing untracked files should be
      preserved until their owner chooses where they belong.
- [ ] Include `finish.md` and other maintained root Markdown documents in
      formatting/quality checks; the current root formatter list checks README
      but omits the spec and this report.

**Done when:** a reviewer can understand, run, and try the project quickly and
verify the technical claims without an engineering walkthrough.

## Work that can follow the first release

These should not distract from the blockers above:

- Paginate/search the roles list and profile history; replace privacy status's
  load-all-records calculation with bounded database aggregates when dataset
  size warrants it.
- Add broader load/soak testing and tune database indexes/pooling using measured
  query behavior. Add keyset pagination where insert/delete activity makes
  offset pagination unreliable.
- Lock the full Python dependency graph, including transitive runtime
  dependencies; current requirements pin direct packages only and setup eagerly
  upgrades dependencies. Use separate minimal production and development
  installations.
- Consider stronger database safeguards for approved profile content and
  role-to-organization relationships as defense in depth. Service guards exist;
  only audit records have explicit mutation triggers today.
- Improve printing/export of interview guides, role cloning, manager
  notifications, and richer review history if pilot feedback justifies them.
- Add multi-organization memberships only if the actual user model needs them.

ATS integration, résumé parsing, aggregate fit scores, applicant ranking,
automated advancement/rejection, and training on hiring outcomes remain outside
the MVP. Additional infrastructure such as Kubernetes, object storage, or a new
queue should be introduced only to solve a demonstrated requirement.

## Release gates

**Synthetic hosted demo:** tasks 1–15 completed or covered by explicitly
documented scope decisions, plus a controlled demo/walkthrough from task 17.
Fresh CI, browser E2E, PostgreSQL and HTTPS staging verification pass;
deployment, rollback, and sensitive-data handling are demonstrated. The content
is clearly labeled synthetic/unvalidated.

**Real candidate pilot:** the synthetic technical gate plus task 16, complete
candidate-data lifecycle enforcement, working rights/accommodation contacts,
scheduled retention, and documented backup/incident handling. Approval records
reference the actual content and release revision.

**Broader production use:** a successful controlled pilot, professional
assessment-validity/fairness review appropriate to the intended use, measured
operational capacity/recovery, and renewed review of scope and controls. Do not
equate a deployed app with a validated employment assessment.
