# Integrated UI review

Initial checkpoint: November 4, 2026, revision `124f887` (shell `34e1749`,
accounts/invitations `f81d530`, privacy `e76ef02`). Application reviewed
read-only; this document is the only owned repository output.

## Findings

No blocking behavior regression found in the exact three UI diffs. Account
versioned updates, self-account restriction, confirmation/cancellation and
return focus remain intact. Invitation stored state is still distinct from
delivery state; uncertain outcomes preserve the retry key and explicit
revoke/reissue instruction. Privacy retains related-history limitations, request
race guards, confirmation and error semantics. Header changes retain session
refocus/race handling, candidate isolation and failed sign-out recovery; stale
sign-out errors are now suppressed once the session is expired.

The reported floating skip link is reproducible in Chromium's scrolled full-page
screenshot, including the new shell, but not in the actual viewport. At mobile
scrollY=600 the unfocused link has viewport top=-84, bottom=-36 and computed
translate `0px -200%`; the viewport screenshot shows no overlay. Keyboard Tab
reveals it and Enter targets `#main-content`. Do not report the capture artifact
as a confirmed user-visible overlap. Prefer viewport captures for this check.

Visually inspected old shell/admin evidence and new desktop accounts, mobile
accounts, invitation uncertainty, privacy audit and scrolled viewport images.
New composition has the neutral canvas, compact record rows, wrapped long
identity/email/reference text and visible text-based states. The account heading
outline reflects existing programmatic focus, not a layout border defect.

## Exact checks

- Live `orca terminal show` displayed `GPT-6-Astra medium fast`; no toggle.
- Read applicable `apps/web/AGENTS.md`, final plan, specification, finish
  review, progress ledger, and installed Next 16.4.1 accessibility/CSS
  documentation.
- Setup installers were no longer running; installed JS lock metadata and Python
  environment existed before checks. This review does not certify clean setup.
- `npm run dev --workspace @iopsych/web -- --hostname 127.0.0.1 --port 3165`:
  actual isolated Next development server, no API or database needed.
- `node /tmp/iopsych-integrated-review.mjs`: 22 renders at 1280×900 and 375×900;
  zero page errors, horizontal overflow or full-document axe WCAG A/AA
  violations; all inspected main links/buttons/inputs/selects at least 44px
  tall. Covers account populated/confirmation/empty/expired, invitation review/
  uncertain/receipt/expired, privacy confirmation/audit/denied. Account Escape
  returns focus, revoke returns focus, retries preserve the idempotency key.
- `node /tmp/iopsych-integrated-shell.mjs`: both widths pass keyboard skip-link
  activation, focus outline, header 44px targets, long identity overflow,
  sign-out retry/expiry/redirect and candidate-header isolation.
- Diagnostic replay captured skip-link geometry plus viewport screenshot. No
  full unit/API suite was duplicated.

All browser API requests were intercepted with synthetic fixtures. Local
evidence: `/tmp/iopsych-integrated-review/{receipt.json,*.png}` and
`/tmp/iopsych-integrated-shell/{results.json,*.png}`; reproducers named above.
These temporary files are not committed or durable release artifacts. The
candidate shell isolation route is `/candidate` (404 body), not assessment E2E.

## Scope and follow-up

The reviewed presentation commits do not change matching, report trace,
assessment evidence or ranking behavior. Trace lineage, uncertainty and
no-ranking/no-automated-decision requirements remain mandatory. Incoming role,
report/evidence and candidate presentation commits and remote Auth0/Resend
reconciliation are not yet present at this checkpoint; recheck their integrated
revision before claiming combined acceptance. In particular preserve
organization display/session-expiry hooks and reconcile expanded delivery states
without weakening stable issuance keys or historical evidence readers.

This is synthetic development-render evidence, not real login/mail/database,
production-build, screen-reader, device, user-study, scientific or pilot
approval. Coordinator owns final serial integration and broad acceptance;
browser fixture owner retains the 3116 stack. Protected services were untouched.

## Integrated five-lane checkpoint

Rechecked coordinator integration `d7fd9c9` in child merge `5f32f96`, including
reports `8bc79f5`, candidate `84becb3`, roles `8a382f9`/`d7fd9c9` and the
previously checked shell/admin changes. The coordinator's superseding
STANDARD/default policy was received and acknowledged; live terminal then showed
`GPT-6-Astra medium` without Fast. No service-tier toggle was performed here.

Read exact incoming diffs and inspected owner screenshots, then independently
rendered the integrated app on owned port 3165 with synthetic intercepted APIs:

- Report reproducer copied to `/tmp/iopsych-review-reports.mjs`, changing only
  origin to 3165 and fixture root to this checkout; `REPORT_PLAYWRIGHT_MODULE`
  and `REPORT_AXE_MODULE` point to existing browser-runner dependencies, and
  `REPORT_RENDER_OUTPUT=/tmp/iopsych-review-reports`. Twelve captures (list,
  loading, detail, evidence, empty, error at both widths) passed; evidence
  dialog focus, Escape restoration, retry, overflow and main/dialog axe checks
  passed.
- `node /tmp/iopsych-review-candidate-render.mjs`: fourteen captures of consent,
  validation, selected answers, review/revisit, pause, submit error/retry and
  acknowledged completion passed; zero main axe violations/overflow, maximum
  column width 672px, buttons/links/choice labels at least 44px. Consent digest
  echo and pre-consent definition gate were asserted.
- `node /tmp/iopsych-review-candidate-states.mjs`: ten additional captures of
  loading, unavailable, declined, storage failure and notice-review-required
  states passed at both widths, with zero main axe violations/overflow.
- `node /tmp/iopsych-review-roles.cjs`: fourteen captures of role list, create,
  draft profile, approved profile, empty, error and loading passed without
  overflow; create-field focus passed and approved main had zero axe violations.
  These use existing Chrome/Playwright dependencies, no installation changes.

Visually inspected the newly integrated mobile report evidence, mobile candidate
review and desktop role records. Historical statements, item choices and
contributions remain visible; confidence explicitly means response completeness,
not probability/performance. Candidate selected statements and skipped blocks
are readable, revisit actions wrap below content, completion has no fit label,
and role/report no-ranking warnings remain. No blocking presentation regression
was found. Selection, scoring, consent/storage/acknowledgement and immutable
profile guards were not changed by this review.

Concrete reconciliation requirement sent to coordinator: at this checkpoint,
`report-trace-contracts.ts` still restricts both the envelope and
question-selection algorithm to `1.0.0`. The remote semantics owner must support
the explicit v2 algorithm in both places while retaining report/trace
consistency and historical v1 checks. Report UI's new version-aware labels alone
do not establish v2 trace compatibility. This is an outstanding integration
dependency, not a newly introduced presentation regression; remote/provider
reconciliation and its runtime checks are outside this checkpoint's acceptance.

All evidence remains local under
`/tmp/iopsych-review-{reports,candidate,roles}`. No application files were
edited, no unit/full suite was duplicated, and the owned dev server was stopped.
The automatic Next AGENTS heading rewrite was restored. Both receipt commits
passed scoped Prettier and `git diff --check`.
