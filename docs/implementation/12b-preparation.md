# 12B preparation handoff

Date: 2026-11-04. Baseline: `3602cb050e82969105828544af3fc08a78c16e32`. Scope:
documentation only in this child worktree. **Preparation complete; full 12B /
original 5B pending.** No app, contract, migration, dependency, setup,
scientific interpretation or approval changes. No database or mail service used.

## Deliverables and ownership

- [Per-screen checklist](../accessibility/checklist.md): 13 screen/state groups,
  shared keyboard/speech/focus/errors/reflow/contrast/motion/touch checks and
  proposed device coverage; missing screens explicitly blocked.
- [Synthetic usability protocol](../accessibility/usability-protocol.md):
  neutral comprehension probes, unaided/assisted rubric and elapsed timing
  definitions.
- [Evidence templates](../accessibility/evidence.md): run/finding/session
  records and agreed axe handoff. Coordinator explicitly accepted that 12A owns
  automatic axe implementation/dependencies under `tests/browser` with
  standalone manifest and lock; stable dialogs/errors, current/prior A/AA tags,
  violations/incomplete and sanitized route-state/browser/revision evidence. No
  duplicate runner added.

These extend the separate read-only 12A/12B gap audit with execution
instructions; they do not supersede its findings or the 12A browser
implementation.

## Executed checks and limits

| Actual command/action                                                                                                                                                                | Result                                                                                                                                                                                        |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `git rev-parse HEAD` and `git status --short` at start                                                                                                                               | Exact assigned baseline above; clean tree.                                                                                                                                                    |
| `rg --files` plus `cat`/`sed`/`rg -n` over final plan, spec, finish report, progress ledger, applicable web AGENTS and screen sources                                                | Read-only source review; mapped actual routes and future surfaces. Large combined output was truncated; targeted sections were reread. No root/ancestor AGENTS found in checked parent paths. |
| W3C WCAG 2.2 reference opened via web tool                                                                                                                                           | Checked criterion mapping against published standard; no conformance claim.                                                                                                                   |
| `node_modules/.bin/vitest run --config apps/web/vitest.config.ts apps/web/app/reports/report-detail.test.tsx 'apps/web/app/candidate/invites/[token]/candidate-assessment.test.tsx'` | Exit 0: 2 files, 10 tests passed in 1.43s. Component tests only, not browser/AT evidence.                                                                                                     |
| `node_modules/.bin/prettier --write docs/accessibility/*.md docs/implementation/12b-preparation.md`                                                                                  | Executed to normalize owned Markdown.                                                                                                                                                         |
| `node_modules/.bin/prettier --check docs/accessibility/*.md docs/implementation/12b-preparation.md` and `git diff --check`                                                           | Exit 0: all four Markdown files formatted; diff whitespace check clean.                                                                                                                       |
| Orca ask/check/heartbeat                                                                                                                                                             | Axe boundary confirmed; checkpoint messages checked.                                                                                                                                          |

Skipped deliberately: full suite, production build, axe run, local server/DB,
manual browser/keyboard/contrast/reflow/mobile checks, screen readers and user
study. This bounded preparation uses source inspection plus existing focused
component tests; completed screens and the separately owned 12A runtime are
needed for integrated results. No runtime was started while shared setup runs;
3107/8107 and DB5547 `iopsych_a11y` remain unused. No manual or human pass is
claimed, and no failing runtime behavior was reproduced here.

## Concrete next-dispatch checks/fixes

Source risks below require reproduction before a browser-defect claim. Owners
are proposed package destinations, not new allocations or approvals.

| Risk / source                                                                                                                            | Next action and acceptance                                                                                                                                                                                                          | Destination                                                                                                                   |
| ---------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| Candidate save label uses `resumedDraft                                                                                                  |                                                                                                                                                                                                                                     | responseSet.responses.length > 0`; storage write catch is separate (`candidate-assessment.tsx`, save effect and status text). | Recheck 9A integration with denied/quota storage; ensure speech/text says saved only after successful write, completion still works. Avoid duplicating active 9A edits. | 9A then 12B A08/A09 |
| Privacy confirmation is conditional inline content without explicit focus/live handling (`privacy-workspace.tsx`, `confirmingDeletion`). | Keyboard/AT reproduce discovery after Prepare anonymization; if missed, associate/announce confirmation and provide deliberate focus/recovery. Verify reversible preparation before destructive confirmation on disposable fixture. | 10B / A13                                                                                                                     |
| Form errors often use alert text without field-level `aria-describedby`/`aria-invalid` (sign-in/create role/profile forms).              | Trigger each validation path; verify field identity/correction available on return focus; add associations where missing and preserve valid input. Alert presence alone is insufficient.                                            | Screen owners / A02–A05                                                                                                       |
| Evidence drawer explicitly calls native `showModal`, focuses Close, restores trigger (`report-detail.tsx`).                              | Preserve behavior; verify actual modal containment, speech, Escape, scroll and return in Safari/Chromium. jsdom cannot certify it.                                                                                                  | 12A/12B A12                                                                                                                   |
| Global reduced-motion override and field focus styling exist (`globals.css`).                                                            | Measure rendered focus contrast and inspect skeleton/hover/progress at reduced motion and zoom; fix only reproduced failures.                                                                                                       | 12B visual follow-up                                                                                                          |
| Sign-in remains token entry; invitation/manager handoff/rights surfaces incomplete at baseline.                                          | Repeat complete checks after 7A/7C/8B/10B integration, including authentication/help and recovery; do not accept a mocked/API path as UI coverage.                                                                                  | Feature owners then 12A/12B                                                                                                   |

## Remaining package gates and assumptions

Full 12B needs completed screens, revision-linked automatic scans, actual
keyboard/screen-reader/device runs, reproduced blockers fixed and retested, and
intended-user comprehension/timing evidence. Human recruitment/recording,
working support contacts, review of content/privacy and any accepted limitations
need accountable owners; none were supplied or invented. The spec sets a median
under ten minutes but no numerical comprehension threshold; protocol reports
observations without inventing one. Scientific ambiguity is routed to 6B/9C. 12C
rehearsal and real-pilot approval remain separate gates. No push/deployment or
external communication beyond authorized Orca coordination occurred.

Commit: identified by this report's containing Git commit, subject
`docs: prepare bounded 12B accessibility and usability evidence`; obtain exact
ID with `git log -1 --format=%H -- docs/implementation/12b-preparation.md`.
