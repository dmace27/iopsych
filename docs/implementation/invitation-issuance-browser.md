# Invitation issuance browser coverage

This slice owns only `tests/browser/invitation-issuance.spec.ts` and this
report. It reads the integrated issuance form/client, production proxy contract,
existing browser fixtures and accelerated implementation plan. No root/ancestor
AGENTS file applies to these files; the web-specific guidance was read for
context. The rendered worker terminal showed `GPT-6-Astra medium fast`; no mode
toggle was performed.

## Cases

- Approved profile options match the actual approved profile response;
  recipient, version and requested expiry appear in a preview before any
  issuance POST. Explicit confirmation sends the strict payload and a UUID
  request key, returns HTTP 201, refreshes history and survives reload.
- A real browser double click while the request is held in flight sends one
  browser POST, disables confirmation/history actions, and records the result.
  The intercepted request continues to the production server without a mock
  response. This checks the UI lock, not backend replay idempotency.
- Expiry values 0, 721 and 1.5 disable review; an explicit same-origin request
  bypassing the form with 721 hours receives HTTP 422 and creates no history
  row.
- The existing manager cannot see the issuance form; a same-organization POST
  also receives HTTP 403.
- A unique synthetic invitation is revoked using the keyboard, focus moves to
  its retained history card, and explicit new issuance for the same recipient
  uses a new key and retains both history records across reload.
- Keyboard review reaches confirmation with Tab and returns with Shift+Tab.
  WCAG-tagged axe scans and horizontal reflow checks run at 320, 375 and 1280
  pixels; manager denial also receives an axe scan. Diagnostics retain rule IDs
  and node counts, without HTML, credentials, candidate URLs or storage.

## Isolation and execution

The existing runner owns a fresh production Next/FastAPI/PostgreSQL stack and a
local capture mailbox on 3116/8116/5556/1136/8136. Its hardcoded ports require
an exclusive handoff from the accounts-browser worker; this slice adds no port
override, fixture, configuration or runner edits. Protected services and
existing databases are not used or reset. All recipients are unique
`@example.invalid` addresses and only those new invitations are revoked. The
existing alpha approved profile is read, not modified. No real mail, provider
call or production secret is needed.

Runner owner requirements: register `invitation-issuance.spec.ts` in the
restricted spec selector and preserve the existing `BROWSER_E2E_RECRUITER` and
`BROWSER_E2E_MANAGER` credentials. No new fixture environment variable is
required. The standalone guard remains mandatory; run only through the owned
runner after the saved installer and exclusive runtime handoff.

## Evidence and remaining gates

Authoring baseline: `eeea1da` (integrated form), updated to `1d269c4` including
the issuance POST proxy before execution. The accounts runner commit `0255fce`
was cherry-picked as `cc00aaf`; that is the tested application baseline, plus
the new spec. The saved root/API installer's rendered completion marker reported
exit 0; `npm ci --prefix tests/browser` installed the separate browser packages.
Accounts-browser explicitly released the runtime before this run.

On 2026-11-04, `bash scripts/browser-e2e.sh invitation-issuance.spec.ts` passed
**6/6 tests, zero skipped, in 6.0 seconds**, with a successful production build
and fresh database migrations through 0010. Chromium was `156.0.8078.4`, axe was
`4.14.0`, and all four axe scans had zero violations. Incomplete findings were
`color-contrast` (4 nodes on manager denial, 194 on each preview width) and
`aria-prohibited-attr` (1 node on each preview width). They remain manual-review
items, not accessibility passes. The runner exited 0, stopped its servers and
removed its own PostgreSQL/mailbox containers and network; runtime ownership was
released to the coordinator.

The coordinator then requested verification with the new delivery fields and
recovery form. Runtime ownership was reclaimed for those targeted checks:

| Application revision              | Result                               | Detail                                                                                                                                      |
| --------------------------------- | ------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------- |
| `cc00aaf` plus initial spec       | 6 passed, 0 skipped, 6.0s            | Original integrated form/proxy baseline above.                                                                                              |
| `7b8a931`                         | 5 passed, 1 failed, 0 skipped, 10.4s | New delivery UI renamed the revoke label from `Stored status` to `Stored invitation state`; two test assertions still used the former copy. |
| `29fe93e` plus updated assertions | **6 passed, 0 skipped, 6.4s**        | Includes integrated delivery API/UI and recovery commit `3111919`; same six requested cases, no application fix made by this worker.        |

The final run again built production assets and migrated a fresh database. Its
four axe scans reported zero violations, with the same incomplete rule IDs;
preview `color-contrast` counts were 269 at each width after adding delivery
rows, manager denial remained 4, and preview `aria-prohibited-attr` remained 1.
Browser/axe versions were unchanged. Final cleanup exited 0 and removed the
owned stack; ports 3116/8116/5556/1136/8136 are released. No full suite was run.

Scoped Prettier and `git diff --check` passed. Standalone strict TypeScript
passed with
`tsc --noEmit --strict --target es2022 --module nodenext --moduleResolution nodenext --skipLibCheck tests/browser/invitation-issuance.spec.ts`.
The build's generated `next-env.d.ts` path changes were restored; no application
edit remains.

The recovery-form revision was exercised by the six normal/denied/invalid
journeys above; terminal conflict and uncertain-retry browser scenarios remain
outside this slice's tested cases.

The synchronous local-mail fixture does not establish queued delivery,
exactly-once delivery, receipt, retry/replay semantics or real-provider
acceptance. Axe incomplete findings require manual review. Full-suite
regression, manual assistive technology testing, intended-user review and
hosted/provider gates remain separate; this slice does not close them.
