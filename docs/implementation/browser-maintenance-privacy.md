# Maintenance and privacy production browser verification

Verification date: 2026-11-04. Application base: `58eaad8`, after integrating
`codex/final-implementation` from `cbcb85a`. This includes role maintenance
`17790e6`, description locking `088be3a`, invitation focus `0a676d6`, and
privacy lifecycle reconciliation through `58eaad8`. This change adds tests and
synthetic runner fixtures only; application fixes belong to their original
commits.

## Journeys

`tests/browser/maintenance-privacy.spec.ts` adds five production-browser cases:

| Journey               | Assertions                                                                                                                                                                                                                                                                                                                                                                                                                             |
| --------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Recruiter maintenance | Create an independent synthetic role through the UI; edit metadata before extraction; extract and save a second profile version; verify description is disabled after versioning; change department/location; reload and verify metadata and both versions survive.                                                                                                                                                                    |
| Archive and keyboard  | Reach archive by Tab; initial focus on Keep role; Tab/Shift+Tab between dialog actions; Escape closes and restores trigger focus; keyboard confirmation archives; maintenance heading receives focus; mutation controls disappear; history and read-only state survive reload.                                                                                                                                                         |
| Manager denial        | Own-tenant role exposes denial and no maintenance actions; actual PATCH and DELETE requests return 403; role title remains unchanged; privacy UI is denied.                                                                                                                                                                                                                                                                            |
| Administrator privacy | Complete a dedicated synthetic candidate assessment; select Role ID and find/select the assessment through the privacy UI; download and remove a real JSON export; cancel then confirm anonymization; verify old export and stale “Anonymized: No” disappear; verify the live-region announcement; a subsequent export fails without a download or export-success announcement; relookup clears selection and disables rights actions. |
| Invitation keyboard   | Dedicated revoke fixture: keyboard cancel retains trigger focus, accepted revocation focuses its surviving record; final pagination removes its button and focuses the first appended record. These are separate tests for revoke and pagination.                                                                                                                                                                                      |

The archive journey never archives either shared seed role. `PRIVACY` and
`FOCUS` are distinct fixture invitations; existing smoke/accessibility/current
tokens are not consumed by the new tests. The existing single-worker suite runs
maintenance before smoke, so the privacy lookup has exactly its independently
submitted assessment. Twenty-six older, expired synthetic invitations provide a
bounded 25-to-34-row pagination journey without generating deliverable bearer
links. Their fixed old creation time keeps the active smoke/revoke fixtures on
page one.

## Execution and results

Run with `scripts/browser-e2e.sh`; install the locked browser dependencies with
`npm ci --prefix tests/browser` when setting up a fresh checkout. The runner
builds Next.js for production and uses the real API/BFF/session/auth/database
contracts, with existing deterministic extraction and local mail adapters.
Requests are restricted to the owned web origin. Runtime ports are
3116/8116/5556/1136/8136; the runner creates and removes its own Compose project
and volumes on each run.

The first attempt built production successfully but could not launch Playwright:
`playwright: command not found` (exit 127). Locked dependencies were then
installed. The second attempt ran all 37 cases: 36 passed, one failed because
the new test incorrectly selected `role=status` for the privacy announcement.
The application uses an `aria-live=polite` region; the test now checks that
actual live region and preserves its lifecycle assertions. No application change
addressed that test locator failure. All role, manager, revoke-focus, and
final-pagination cases passed on that attempt, including the strict row focus
destinations.

Final fresh full rerun: **37 passed (31.2s)**, exit 0, using Chromium
`156.0.8078.4` and Playwright `1.64.1`. The five new cases and all 32 existing
cases passed. Production build and migrations through `20261104_0009` completed;
the owned containers, network, volumes, downloads, and temporary artifacts were
cleaned on exit. No outstanding application failure was observed in these
journeys after the integrated fixes.

Runner safety checks: `17 passed` with
`.venv/bin/pytest tests/browser/test_scaffold.py -q`. Ruff passes for the
modified Python files using `--config apps/api/pyproject.toml`; Prettier formats
the new spec and config, and `git diff --check` passes.

## Evidence boundaries

No credentials, raw exports, screenshots, videos, or traces are retained in this
report. The export download is deleted immediately; temporary Playwright output
and server logs are cleaned by the existing runner. The runner redacts generated
credentials from displayed diagnostics. Only synthetic `example.invalid`
recipients and an owned local mailbox are used.

Native Chromium keyboard/focus assertions are browser evidence, not a manual
screen-reader claim or complete accessibility certification. Existing automated
axe findings and incomplete checks remain subject to the prior browser reports.
No mobile-browser, manual assistive-technology, or real-mail validation is
claimed. The earlier DR-01 and DR-02 failures remain documented in the discovery
review and fix handoff reports; this verification does not erase those findings.
