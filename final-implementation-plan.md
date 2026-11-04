# IOPsych: final implementation plan

Prepared November 4, 2026 against revision `f5224c9`.

This is the remaining-work plan. It continues the package format of
`mvp-spec.md` section 17, using phases 6–12 so new tasks cannot be confused with
the original packages. It does not declare original phases 0–4 fully complete.
The original product specification remains authoritative; `finish.md` supplies
the detailed release findings that this plan organizes into executable work.

## Current baseline

Preserve the existing contracts, tenant authorization, audit protections,
immutable profiles, consent gates, scoring, persisted reports, extraction
validation, and privacy tools. Extend them rather than rebuilding them.

The latest review ran 423 passing tests with two PostgreSQL-dependent tests
skipped. These are existing test results, not evidence of a complete browser
journey or a deployed release. The app currently runs locally using ignored
configuration, a seeded synthetic database, and manually generated tokens. That
local setup does not fix the committed startup template or complete login.

## Working agreement

- Implement one named package per task; include its necessary integration work.
- Before changing a shared contract, document its shape, compatibility impact,
  and migration strategy in the task handoff.
- Preserve organization isolation, human approval, candidate consent, immutable
  historical records, and the absence of composite scores or candidate ranking.
- Use synthetic data for implementation, screenshots, tests, and rehearsal.
- Never commit local configuration, signing keys, access tokens, or invite URLs.
- A package is complete only when its acceptance checks pass. Record failures,
  skipped checks, and external dependencies explicitly.
- Every handoff lists changes, migrations, commands/results, remaining issues,
  and the next eligible package. Record completion evidence by revision.
- Scope reductions must update the specification and acceptance criteria in a
  recorded product decision. An omitted feature is not silently complete.

## Phase 6: setup, decisions, and version compatibility

| Package                                              | Implementation scope                                                                                                                                                                                                                                                                                                                                              | Dependencies        | Done when                                                                                                                                                                                                                                                        |
| ---------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **6A — Reproducible local setup**                    | Fix the unquoted retention statement; replace shell execution of configuration with dotenv-aware loading while preserving host/port overrides. Use lockfile-based JavaScript installation. Document runtime versions, database setup, port overrides, and a controlled local synthetic-login method.                                                              | Existing foundation | A fresh checkout following only the README starts both apps and PostgreSQL, applies migrations, seeds/verifies isolated tenants, and authenticates a synthetic user without hand-editing a JWT. The actual launcher is exercised by a startup regression.        |
| **6B — Product and interpretation decisions**        | Record structure comparison semantics with four low/high examples; decide identity provider, one-organization-per-user versus memberships, delivery provider, hosting topology, draft-resume promise, optional context, external versus in-app interview notes, and manager review states. Distinguish synthetic-demo decisions from real-pilot content approval. | None                | A decision record resolves each item, identifies the owner, and updates conflicting specification text. Engineering can proceed without silently guessing assessment meaning or removing required journeys.                                                      |
| **6C — Immutable assignment and historical readers** | Bind invitations to assessment/scoring versions; retain immutable definitions. Serve assigned definitions after consent. Add version-aware matching/report readers and explicit handling of unknown versions. Define reviewed/retired assignment policy and legacy invitation backfill.                                                                           | 6B                  | Existing invitations, saved drafts, submitted assessments, and v1 reports survive an upgrade. Retired definitions remain readable where required; real-pilot assignments reject unreviewed definitions. Migrations are tested over populated prior-version data. |

Recommended prompts:

- **6A:** “Implement package 6A from `final-implementation-plan.md`. Make clean
  local setup reproducible, fix environment loading, and provide controlled
  synthetic development login. Verify the documented startup path.”
- **6B:** “Prepare the decisions and concrete options required by package 6B.
  Record approved choices and update the specification. Identify decisions
  requiring an accountable product or I-O reviewer; do not invent their
  approval.”
- **6C:** “Implement package 6C. Pin assessment assignments and preserve
  historical scoring/report compatibility. Include populated-data upgrade
  tests.”

## Phase 7: internal accounts and complete role review

| Package                                          | Implementation scope                                                                                                                                                                                                                                                                 | Dependencies                  | Done when                                                                                                                                                                                                                     |
| ------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **7A — Provider login and session recovery**     | Integrate the selected identity provider, callback and signature/claim verification. Add visible sign-out, expired-session recovery, account/organization context, and safe local-path `returnTo`. Keep synthetic login restricted to explicit local/demo policy.                    | 6A, identity decision in 6B   | Recruiter and manager can sign in independently without pasted JWTs. Callback failures, expiry, sign-out, invalid claims, and open redirects are tested. Database permissions remain authoritative.                           |
| **7B — Provisioning and account administration** | Provide controlled organization/admin setup and user provisioning, role changes, deactivation, and audits. Implement memberships/switching only if selected; otherwise record and present the single-organization limit.                                                             | 7A, membership decision in 6B | An administrator can grant, change, and revoke access through a documented workflow. Disabled users and changed permissions are enforced on subsequent requests; cross-tenant access and switching, if supported, are tested. |
| **7C — Manager handoff and role maintenance**    | Add explicit submission for review, request edits/reject with reason, attribution, and audit. Preserve immutable versions and approval gates. Expose role metadata editing and archival. Implement the chosen separate notes workflow or document the approved external destination. | 6B, 7A                        | A recruiter hands a profile to a manager, receives actionable feedback, revises it, and obtains approval in the browser. Permissions, stale versions, archived roles, and immutable approval behavior are tested.             |

Recommended prompts:

- **7A:** “Implement package 7A. Replace token-paste login with the selected
  provider and complete sign-out/session recovery while preserving tenant
  authorization.”
- **7B:** “Implement package 7B. Complete controlled provisioning, permission
  changes, deactivation, and the approved organization-membership policy.”
- **7C:** “Implement package 7C. Complete manager review handoff and role
  maintenance with versioned decisions, reasons, and audit evidence.”

## Phase 8: candidate invitation delivery and management

| Package                                                 | Implementation scope                                                                                                                                                                                                                                                                                                          | Dependencies                | Done when                                                                                                                                                                                                                                                                                                                                                 |
| ------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **8A — Reliable delivery and invitation lifecycle API** | Configure the chosen transactional email provider. Add bounded tenant-scoped invite discovery and issuance idempotency. Resolve the send-before-commit failure window with a durable, documented delivery/recovery design. Support failure, revoke/reissue, and relevant bounce/webhook handling. Pin assignments through 6C. | 6C, delivery decision in 6B | A staging invite reaches a controlled mailbox and opens a valid consent page. Provider timeout/uncertain acceptance, duplicate requests, and database/audit failure have recoverable outcomes. Raw tokens stay out of ordinary storage/logs/API responses; any queued delivery credential has explicit encryption, access, expiry, and deletion controls. |
| **8B — Recruiter invitation UI**                        | Add shared contracts, allowed proxy routes, API client methods, email/expiry/purpose/preview form, and invitation status list. Show delivery, consent, submission, expiry, and revocation states with permitted actions.                                                                                                      | 8A, 7C                      | Recruiter/admin/manager permissions match the API. Create-role → manager approval → invitation works entirely in the browser. Unapproved/archived profiles, duplicate clicks, invalid expiry, tenant violations, and provider errors are handled and tested.                                                                                              |

Recommended prompts:

- **8A:** “Implement package 8A. Complete configured email delivery, invitation
  discovery, issuance idempotency, and recoverable delivery failures with secure
  token handling.”
- **8B:** “Implement package 8B. Build and integrate recruiter invitation
  management against the lifecycle API, including all loading/error/permission
  states.”

## Phase 9: candidate recovery and traceable reports

| Package                                                     | Implementation scope                                                                                                                                                                                                                                                                                                                                                                                                      | Dependencies | Done when                                                                                                                                                                                                                                                                       |
| ----------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **9A — Honest device persistence and recovery**             | Handle storage getter exceptions and write failures; allow in-memory completion. Clear stale/incomplete snapshots correctly. Add draft expiry, minimal answer-free completion receipts, legacy cleanup, clear-device/save-exit actions, shared-device guidance, and unavailable-invite recovery.                                                                                                                          | 6C           | Candidates complete with storage disabled; save labels reflect successful writes; reload restores current choices; incomplete edits cannot resurrect stale answers. Completed responses are not kept indefinitely on the device.                                                |
| **9B — Progress and candidate context**                     | Implement consent-gated server draft persistence if selected, including conflict/idempotency and version behavior. Implement optional context if retained, with validation and export/retention/deletion coverage. Otherwise execute the recorded scope revision and accurately describe device-only resume/context omission.                                                                                             | 6B, 6C, 9A   | The advertised resume/context behavior matches the API and UI. Tests cover reload, cross-device behavior if promised, assigned versions, skips, expiry, and unauthorized draft access.                                                                                          |
| **9C — Matching correction and item-level report evidence** | Apply the approved structure semantics across both languages, extraction instructions, fixtures, labels, and explanations. Publish a new algorithm version if behavior changes. Extend reports/drawers with exact versioned block/item references, statements, relevant most/least/skip choices, scoring thresholds, evidence-completeness confidence, rule, and question provenance. Preserve old report interpretation. | 6B, 6C       | Every signal traces to exact role evidence and contributing assessment choices. Complete/skipped/low-confidence cases and four structure extremes agree across languages. Historical reports remain readable as saved; confidence is not presented as a calibrated probability. |

Recommended prompts:

- **9A:** “Implement package 9A. Fix candidate device persistence and recovery,
  including storage denial, truthful save status, stale snapshots, expiry, and
  minimal completion receipts.”
- **9B:** “Implement package 9B using the recorded progress/context decisions.
  Ensure the documented promise matches implemented behavior and privacy
  handling.”
- **9C:** “Implement package 9C. Apply approved structure semantics and provide
  exact item-level report traceability while preserving historical results and
  cross-language parity.”

## Phase 10: complete candidate-data lifecycle

| Package                                           | Implementation scope                                                                                                                                                                                                                                                                                                                                | Dependencies                       | Done when                                                                                                                                                                                                                                    |
| ------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **10A — Privacy lifecycle and rights**            | Cover unopened/expired, declined, revoked, consented-but-unsubmitted, draft, submitted, and anonymized records. Freeze notice text and applicable policy at consent/assignment. Define and implement approved withdrawal behavior, identity verification after link expiry, and correction handling without silently overwriting immutable history. | 6B, 6C, 8A, 9B                     | Every candidate-data category has a defined deadline and enforceable rights path. Export/deletion includes draft/context data and derived reports as appropriate. PostgreSQL tests cover export/deletion/submission/report-generation races. |
| **10B — Practical privacy administration**        | Add bounded permitted discovery by candidate/role/invitation references and related-event audit traversal. Integrate export, deletion, correction/withdrawal handling, support guidance, and verified contact details into the chosen operational workflow.                                                                                         | 10A, 7B                            | An administrator can locate and complete a rights request without an engineer supplying an assessment UUID. Permissions, download behavior, audit relationships, and empty/error states are tested.                                          |
| **10C — Scheduled retention and deletion replay** | Schedule cleanup; drain multiple bounded batches safely; measure overdue records and missed runs. Define and implement deletion replay/tombstones after backup restore under the approved retention policy.                                                                                                                                         | 10A, deployment scheduler from 11A | An unattended rehearsal cleans all due lifecycle categories, handles a backlog, preserves required non-identifying audits, and alerts on failure. A restore rehearsal does not silently resurrect deleted candidate data.                    |

Recommended prompts:

- **10A:** “Implement package 10A. Complete candidate-data deadlines,
  consent-policy snapshots, withdrawal/correction policy, and rights handling
  across the entire lifecycle.”
- **10B:** “Implement package 10B. Make privacy administration usable through
  bounded discovery, related audit history, and complete rights-request
  workflows.”
- **10C:** “Implement package 10C. Schedule and monitor retention, handle
  backlogs, and verify deletion replay after restore.”

## Phase 11: bounded runtime, deployment, and operations

| Package                                                 | Implementation scope                                                                                                                                                                                                                                                                                                                                                                                | Dependencies                                                 | Done when                                                                                                                                                                                                                                                                       |
| ------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **11A — Reproducible staging and release packaging**    | Implement the chosen topology, API/web production packaging, shared Python/assets inclusion, managed PostgreSQL, separate staging, TLS, private API access, secret injection, runtime/migration privileges, and controlled migrations. Bind local PostgreSQL to loopback. Add revision-tagged staging deployment and rollback steps.                                                                | Hosting decision in 6B; initial packaging can start after 6A | A clean checkout deploys staging with correct assets and schema, no automatic real-pilot seeding, and graceful process shutdown. A controlled rollback/forward-fix rehearsal preserves data and historical interpretation. Final release gates depend on 12A–12C.               |
| **11B — Configuration, readiness, and resource bounds** | Reject sample/missing secrets and invalid public configuration in hosted mode. Separate liveness/readiness with database/schema checks. Bound bodies, upstream timeouts, extraction retry duration/output/cost/concurrency, and duplicate requests. Add shared ingress limits and prevent proxy traffic sharing one unfair per-browser budget. Address blocking synchronous work in async handlers. | 6A, 7A, 8A; staging verification uses 11A                    | Bad hosted configuration fails before traffic; oversized/stalled/burst requests remain bounded; slow dependencies do not block unrelated requests. Readiness avoids paid-provider probes. A configured extraction provider is exercised with synthetic text in staging.         |
| **11C — Observability and recovery**                    | Add correlation/release IDs, structured allowlisted logs, safe error tracking, latency/error/retention/delivery metrics, and actionable alerts. Redact across API, web, ingress, email, and telemetry. Configure encrypted backups, recovery objectives, restore verification, and accountable responders.                                                                                          | 11A; provider telemetry integrates 8A/11B                    | A rehearsed failure produces a useful alert without token/PII leakage. Backup restore meets recorded objectives and integrates 10C deletion replay before candidate-data use. Track the specified operational/usability metrics without ranking or hiring-outcome optimization. |

Recommended prompts:

- **11A:** “Implement package 11A using the chosen topology. Produce
  reproducible production packaging, staging deployment, controlled migration,
  and tested rollback instructions.”
- **11B:** “Implement package 11B. Validate hosted configuration, provide
  readiness, and bound request, provider, rate-limit, and blocking-work
  behavior.”
- **11C:** “Implement package 11C. Add safe operational visibility, actionable
  alerts, encrypted backup/restore verification, and recovery ownership.”

## Phase 12: finish original 5A, 5B, and 5C and publish evidence

| Package                                                         | Implementation scope                                                                                                                                                                                                                                                                                                                                                                                                                                 | Dependencies                                                                                      | Done when                                                                                                                                                                                                                                                                                                                  |
| --------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **12A — Full browser and database E2E (original 5A)**           | Add a production-build browser runner, isolated PostgreSQL data, controlled mailbox, and deterministic extraction fixture. Cover separate recruiter/manager/admin identities and the full role-to-report-to-rights journey plus failures. Test real HTTPS cookie/CSP behavior in staging, populated migration upgrades, native dialogs, privacy downloads, and version upgrades. Refresh dependency/history secret scans and required hosted checks. | Feature packages 7–10 and 11A/11B; runner scaffolding may start earlier                           | Hosted CI exercises the full journey and required negatives with zero required skips. Real configured-provider smoke checks run separately in staging. Durable evidence identifies exact revision, environment, commands, results, and limitations; branch/release checks are configured.                                  |
| **12B — Accessibility and usability (original 5B)**             | Run browser accessibility scans and manual keyboard/screen-reader, focus, contrast, zoom/reflow, mobile, reduced-motion, touch-target, copy, recovery/support checks across every screen. Test comprehension and completion time with intended users using synthetic data.                                                                                                                                                                           | Completed screens and 12A runner; audits may run incrementally                                    | A WCAG 2.2 AA baseline checklist records browsers/devices, findings, fixes, and accepted limitations. Blocking issues are resolved. Measured results address under-ten-minute completion, consent comprehension, and interpretation of confidence and “worth discussing.”                                                  |
| **12C — Runbooks, rehearsal, and pilot approval (original 5C)** | Write deployment/rollback, incident, key-rotation, support/accommodation, privacy/correction/withdrawal, retention, backup, and user-training procedures. Run a synthetic staging rehearsal. Name owners and obtain actual I-O/content and privacy reviews before real candidate use; replace placeholder contacts.                                                                                                                                  | 10C, 11A–11C, 12A, 12B                                                                            | The section-16 launch checklist has revision-linked evidence, accountable owners, and documented sign-off. Rehearsal includes login, delivery, candidate flow, reporting, rights, cleanup, alerting, restore/rollback, and stop criteria. Technical completion and real-participant authorization are recorded separately. |
| **12D — Controlled demo and project handoff**                   | Publish a synthetic demo with controlled access/reset and bounded email/extraction usage. Add walkthrough, screenshots/video, architecture and engineering decision records, measured results, license, contribution/setup guidance, release notes, and honest limitations. Label historical documents and extend formatting to maintained root plans/specs.                                                                                         | 12A–12C technical release gate; real-candidate approval is not required for a synthetic-only demo | A reviewer can run and try the project without an engineer, verify its claims, and distinguish demonstrated behavior from unvalidated assessment claims. Preserve unrelated local work when tidying documentation.                                                                                                         |

Recommended prompts:

- **12A:** “Implement package 12A and close original 5A. Add production
  browser/PostgreSQL E2E, full negative paths, upgrade tests, and
  revision-linked hosted verification evidence.”
- **12B:** “Implement package 12B and close original 5B. Audit and fix
  accessibility/usability across all screens and document measured evidence and
  remaining limitations.”
- **12C:** “Implement package 12C and close original 5C. Produce operational
  runbooks and a synthetic staging rehearsal. Record external reviews/sign-offs
  accurately; do not treat missing owner approval as an engineering task that
  has passed.”
- **12D:** “Implement package 12D. Deliver a controlled synthetic demo and
  credible project documentation with reproducible evidence and explicit
  limitations.”

## Execution order

Default sequence:

1. **6A → 6B → 6C**: make setup reliable, resolve choices, establish
   compatibility.
2. **7A → 7B → 7C**: complete accounts and manager workflow.
3. **8A → 8B**: make invitations usable from the browser.
4. **9A → 9B → 9C**: complete recovery, progress/context, and report evidence.
5. **10A → 10B**: close lifecycle and administrative gaps.
6. **11A → 11B → 11C → 10C**: deploy, bound, observe, and schedule cleanup.
7. **12A → 12B → 12C → 12D**: finish verification, rehearsal, and handoff.

Dependencies in the tables govern eligibility. Decision preparation, deployment
packaging, test-runner scaffolding, and incremental audits can begin earlier
where their stated dependencies are satisfied. This plan does not require
parallel agents; use separate tasks only when requested and coordinate shared
contracts and migrations before integration.

## Release gates

**Working local demo:** 6A, a controlled development identity path, seeded
database, and accurate instructions. State which external features require
configuration. This is useful for development but does not close the hosted
gate.

**Hosted synthetic MVP:** all technical packages complete, with any scope
changes explicitly recorded; original 5A/5B/5C technical acceptance
demonstrated; controlled demo available. Full browser, PostgreSQL, HTTPS
staging, deployment, rollback, retention, and restore checks have current
revision-linked evidence.

**Real candidate pilot:** hosted technical gate plus actual
content/interpretation review, privacy approval, working rights/accommodation
support, trained users, scheduled data lifecycle enforcement, and accountable
owner sign-off in 12C. Do not substitute fixture review flags or code coverage
for those approvals.

## Coverage of the previous remaining-work review

| `finish.md` task                     | Packages closing it |
| ------------------------------------ | ------------------- |
| 1 — First-run setup                  | 6A                  |
| 2 — Structure policy                 | 6B, 6C, 9C          |
| 3 — Identity workflow                | 7A, 7B              |
| 4 — Invitation delivery              | 8A                  |
| 5 — Recruiter invitations            | 8B                  |
| 6 — Browser persistence              | 9A                  |
| 7 — Assignment/report versions       | 6C                  |
| 8 — Item-level explainability        | 9C                  |
| 9 — Remaining product journeys       | 6B, 7B, 7C, 9B, 10B |
| 10 — Privacy lifecycle               | 10A–10C             |
| 11 — Runtime hardening               | 11B                 |
| 12 — Deployment                      | 11A                 |
| 13 — Observability/recovery/runbooks | 11C, 10C, 12C       |
| 14 — E2E evidence                    | 12A                 |
| 15 — Accessibility/usability         | 12B                 |
| 16 — Pilot operations/approval       | 12C                 |
| 17 — Portfolio credibility           | 12D                 |

## Deliberately later work

Keep the existing specification's exclusions: ATS integration, resume parsing,
composite fit scores, candidate ranking, automatic advancement/rejection, and
training on hiring outcomes. Kubernetes, new queues, and other infrastructure
are choices only where a demonstrated requirement justifies them.

Broader role/profile search and pagination, privacy dashboard aggregation,
load/soak tuning, full transitive Python locking, extra database defense in
depth, printing/export polish, cloning, and richer notifications remain optional
follow-ups unless measurements or the chosen release topology make them
necessary to meet a package's acceptance criteria. Multi-organization
memberships are required only if selected in 6B; otherwise the limitation must
be explicit.
