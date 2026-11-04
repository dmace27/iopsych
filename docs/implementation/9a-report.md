# 9A bounded device-storage handoff

Date: 2026-11-04. Base: `3602cb050e82969105828544af3fc08a78c16e32`.
Implementation commit: `44f3228`
(`fix(web): make candidate device persistence honest and bounded`). This report
is a separate documentation commit. Full package 9A acceptance remains pending
6C integration.

## Delivered

- Guarded access to the localStorage getter; denied access no longer makes a
  valid invite fail. Server acknowledgement still completes the in-memory
  journey.
- Save status follows actual write results, with explicit partial-block and
  failure messages. Navigation says Continue rather than promising a save.
- Empty snapshots remove prior drafts. Replacement removes the old snapshot
  first, so quota failure cannot restore older complete answers when removal
  works.
- Drafts and receipts expire on access after 24 hours, with invitation expiry
  additionally limiting loads. Invalid state is removed best-effort.
- Device receipt contains only assessment ID and submission timestamp. Legacy
  answer-bearing completion records are purged rather than treated as server
  acknowledgement. Server-confirmed completion and decline attempt to clear both
  device keys.
- Save and exit pauses the interface; clear-device removes this invitation's
  local data and pauses without immediately autosaving. Failed saves remain on
  the active page; failed cleanup directs users to browser settings.
- Device-only, complete-block-only recovery and shared-device/offline cleanup
  limits are explicit. Unavailable invites offer retry and sender-contact
  guidance.
- No API/shared schema, dependencies, migration, scoring, or assignment behavior
  changed. A private DeviceReceipt type in candidate-storage.ts avoids modifying
  candidate-contracts.ts.

## Actual validation

Commands run from this child worktree (web commands from `apps/web` unless
noted):

- `npx vitest run 'app/candidate/invites/[token]/candidate-assessment.test.tsx'`:
  initial component pass, 8/8.
- `npx vitest run lib/candidate-storage.test.ts 'app/candidate/invites/[token]/candidate-assessment.test.tsx'`:
  final pass, 17/17 across two files, zero skips. Covers getter denial through
  full submission, quota failure, retries, stale incomplete edits/reload, device
  expiry/invite deadline, malformed/legacy cleanup, minimal receipt, removal
  failures, and save/clear actions.
- `npx eslint lib/candidate-storage.ts lib/candidate-storage.test.ts 'app/candidate/invites/[token]/candidate-assessment.tsx' 'app/candidate/invites/[token]/candidate-assessment.test.tsx' --max-warnings=0`:
  final exit 0. Initial run flagged synchronous storage-result state in the
  effect; the narrow suppression documents why external write outcome must
  update status.
- `npx next typegen && npx tsc --noEmit`: type generation and final typecheck
  exit 0. Initial direct tsc identified missing generated PageProps plus newly
  introduced narrowing/test-literal errors; corrected those errors and generated
  route types. Restored the generated next-env.d.ts change to preserve
  ownership.
- One intermediate focused rerun exposed an existing initial-focus timing race
  in the keyboard consent test; it now waits for initial heading focus before
  moving focus to consent. Final rerun passed.
- Root `npx prettier --write` on the four owned code/test files and
  `npx prettier --check` on those files passed; final report formatted
  separately.
- `git diff --check`: passed before implementation commit.
- Read installed Next guide
  `node_modules/next/dist/docs/01-app/03-api-reference/01-directives/use-client.md`
  before edits, along with web AGENTS and requested
  planning/specification/progress documents.

No full suite, production build, database, network mail, browser E2E, or manual
accessibility run: intentionally skipped for this bounded storage slice. No
services launched; reserved ports 3105/8105/5545 and iopsych_9a database were
unused. No dependency install was run, avoiding the concurrent setup hook.

## Assumptions, limits, and remaining gates

The 24-hour device recovery cap is an implementation default, not an approved
server-retention policy. Product/privacy owners still own final retention and
recovery promises. Partial blocks stay in memory and are explicitly not
recoverable after reload; the shared response contract only accepts complete
choices or skips.

Cleanup is per invitation and on access, not a background timer or remote
erasure guarantee. A browser that denies removal can retain earlier data; the
interface reports failed explicit cleanup and directs users to browser settings.
No claim is made to erase offline devices, other invitations, or other open
tabs. When an unavailable invite API response supplies no invitation ID, this
slice cannot safely identify its storage key from the opaque bearer token;
recovery guidance remains honest and browser site-data cleanup is available.

Legacy completion answers are deliberately discarded for privacy; only server
state establishes submission. Existing valid, unexpired v1 drafts retain their
complete-block recovery path. No historical-version migration or assignment
interpretation is claimed.

6C's consent-gated definition/assignment endpoint must be integrated in a
subsequent UI slice, followed by historical draft/version tests. Full 9A
acceptance, 9B server-progress/product decisions, cross-tab behavior,
real-browser storage/accessibility verification, and broader release/pilot
approval gates remain open. There is no blocker to reviewing or integrating this
bounded commit, and no external approval is invented.
