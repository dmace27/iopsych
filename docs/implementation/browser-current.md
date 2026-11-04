# Current production browser evidence

Date: November 4, 2026. Application baseline: `9de7fd4`, which already includes
`8865f8d` and its consent-reflow and Create role cancellation-focus fixes.
Environment: macOS 26.6.2, Node 24.21.0, npm 11.19.0, Playwright 1.64.1,
Chromium 156.0.8078.4, axe-core 4.14.0. Scope: incremental phase 12A/12B
evidence under `final-implementation-plan.md`. No application changes,
dependency changes, migrations, or new approval claims.

## Runtime and fixture ownership

Every run used `bash scripts/browser-e2e.sh`: a production Next build, a fresh
uniquely named PostgreSQL/Mailpit Compose project, migrations, synthetic seed,
and deterministic extraction. Exclusive loopback ports: web 3116, API 8116,
PostgreSQL 5556, SMTP 1136, mailbox 8136. The runner rejects ambient
credentials, dotenv files, proxies, remote Docker contexts, and occupied ports
before startup. It removes its servers, containers, volumes, and temporary
browser artifacts. No existing database or unrelated services were used.

The dedicated `REVOKE` invitation is an additional runner-created synthetic
credential, required by the standalone browser guard. Its email is
`revoke@example.invalid`. Only the new invitation test revokes it. Original
INVITE/COMPLETE/DENIED/QUOTA/CLEAR ownership is preserved; the accessibility
matrix still reads INVITE before the smoke test declines it. The saved-report
trace assertions extend the existing report-generation case after COMPLETE's
single submission, so no second test consumes that credential. Mailbox counting
and diagnostic redaction include the extra credential automatically.

## Added coverage

- Invitation history reached through the role profile, active fixture visible,
  axe and reflow at 320/375/1280px, native-confirm cancellation, successful
  revocation, status announcement, refresh/reload persistence, and rejected
  candidate access after revocation. Candidate pages omit internal navigation.
- Recruiter name, role and organization in account navigation; keyboard
  activation of Sign out; actual API session rejection; safe invitation
  `returnTo` restoration after signing in; Roles navigation.
- Separate manager account context and invitation-management permission denial.
- Saved report reopened and reloaded before its historical Autonomy drawer is
  checked at 320/375/1280px. Four ordered historical statements must match the
  immutable v1 definition; rating-band and completeness text must appear. Checks
  include initial close-button focus, modal Tab behavior, Escape, trigger-focus
  restoration, drawer horizontal bounds and axe scans.

## Results

The unchanged baseline production matrix passed **29/29**, zero failures and
zero skipped, in **21.5 seconds** of browser execution. This independently
confirms both formerly failing assertions: consent at 320px and cancellation
focus return. Its 44 axe scans reported zero violations; 39 scans had
`color-contrast` incompletes (1–10 nodes per affected scan).

First expanded run: **30 passed, 2 failed, zero skipped** (31.4 seconds). Both
failures concerned new test assumptions: the manager alert locator also matched
Next's route announcer, and the drawer expected one Tab to immediately wrap onto
its sole button. The manager locator now scopes to main; native modal focus
diagnostics allow browser chrome while rejecting background-page controls. No
application assertion was waived and no app change was made. The failed drawer
case stopped at 320px; its later widths were unexecuted in this first expanded
run.

Final expanded production run on the same application revision with the
specifications committed alongside this report: **32 passed, zero failed, zero
skipped** (28.8 seconds, runner exit 0). This includes all 18 existing
accessibility cases, all 11 smoke cases (with the historical drawer extension),
and three new current-feature cases. No real application bug was reproduced.

| Scan group                                    | Scans | Violations | Scans with contrast incomplete | Incomplete nodes per affected scan    |
| --------------------------------------------- | ----: | ---------: | -----------------------------: | ------------------------------------- |
| Existing accessibility matrix                 |    17 |          0 |                             14 | 3–6                                   |
| Smoke including historical drawer             |    30 |          0 |                             25 | 1–10                                  |
| Invitation list before revoke, 320/375/1280px |     3 |          0 |                              3 | 46 each                               |
| Invitation list after revoke/reload, 1280px   |     1 |          0 |                              1 | 45                                    |
| Manager denial, 1280px                        |     1 |          0 |                              1 | 4                                     |
| Total                                         |    52 |          0 |                             44 | Counts are per scan, not unique nodes |

All incompletes were `color-contrast`; none was resolved manually. The three
historical drawer scans had no violations or incompletes. At each drawer width,
four forward Tabs produced BODY (browser boundary), DIALOG, BUTTON, BODY; no
background page control received focus. Escape and trigger focus restoration
passed from that state. This is limited native-dialog evidence, not a claim that
browser chrome was inspected or a complete focus-order audit was done.

Runner safety regression tests:
`.venv/bin/pytest tests/browser/test_scaffold.py -q` passed **17/17**. Ruff
lint/format checks on the runner passed.

## Evidence limits

Automated axe incompletes require manual review; passing browser assertions do
not establish WCAG conformance. No manual screen-reader, contrast, real zoom,
real touch/mobile-device, intended-user comprehension or completion-time test
was performed. Narrow CSS viewports are reflow evidence, not actual 400% zoom.
The historical test reads a saved v1 report; it does not perform a populated
version-upgrade rehearsal. No configured-provider/staging/HTTPS deployment or
hosted CI was exercised. Privacy UI changes arriving after this baseline are
outside this run and need integration verification.

No screenshots, videos, Playwright traces, tokens, mailbox bodies, raw exports,
or browser storage are retained in this report or committed. Console evidence
contains sanitized rule/count summaries only. Full phase 12A/12B acceptance
remains open; the next eligible work is combined integration verification and
manual accessibility/staging evidence owned by the coordinator.
