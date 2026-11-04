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
