# 12B automated browser matrix

2026-11-04. Scope: `tests/browser/accessibility.spec.ts` and this report only.
Uses the existing isolated production runner; no app fixes or acceptance
waivers. This is incremental browser evidence, not WCAG conformance or full 12B
acceptance.

## Method and isolation

The existing `scripts/browser-e2e.sh` builds the production web application,
creates a fresh disposable PostgreSQL/Mailpit project, seeds synthetic
identities, and runs Chromium on the owned origin `http://127.0.0.1:3116`. API
8116, PostgreSQL 5556, SMTP 1136 and Mailpit HTTP 8136 are exclusive to this
dispatch. The runner rejects inherited destination/credential configuration and
occupied ports, redacts its generated credentials, disables
screenshots/trace/video, and removes temporary browser output and its own
resources on exit. Browser requests are restricted to the owned web origin. No
existing database is reset.

The new matrix only reads the INVITE consent landing; it never accepts or
declines any invite and never uses COMPLETE, CLEAR, DENIED or QUOTA credentials.
Existing smoke tests retain ownership of those mutations. Each matrix test has a
fresh browser context and authenticates independently with the runner's
recruiter. The runner executes the alphabetically earlier accessibility file
before smoke's consent mutation; a consent test run after that mutation would
need a fresh runner. No consent-state fixture independence beyond this read-only
boundary is claimed.

## Coverage and interpretation

- A02 sign-in, A03 roles list, A04 seeded profile, A07 consent landing and A10
  invalid invitation: 320, 375 and 1280 CSS-pixel widths at 800px height.
- Axe WCAG 2 A/AA, 2.1 A/AA and 2.2 AA tags: all violations fail; incomplete
  rule IDs/counts are retained for manual review. Accessible names and target
  spacing are covered by applicable axe rules, not inferred from screenshots.
- Reflow measures document width and control horizontal bounds before and after
  WCAG text-spacing overrides. Target geometry logs only element tags and
  rounded dimensions. Small targets require axe spacing/exception analysis; raw
  geometry alone is not a WCAG failure.
- Reduced-motion emulation before loading and toggled during use checks computed
  animation/transition duration and scroll behavior, including pseudo-elements.
  This is a product preference check, not an AA animation-conformance claim.
- A separate keyboard-created draft exercises ArrowRight/ArrowLeft rating
  changes, checked state, keyboard focus and rendered radio focus-ring styling
  without changing a seeded role. Its desktop viewport uses Playwright’s
  1280×720 default; its reflow check uses 320×800.
- Keyboard-only sign-in covers skip-link reachability, native required-field
  validation, invalid credentials and recovery. Roles covers form entry focus,
  native validation, cancellation and focus return. Consent checks Tab/Shift+Tab
  between choices without activating either. Unavailable checks keyboard retry.

320 CSS pixels approximates the reflow width of a 1280px viewport at 400% zoom;
it is not an actual browser zoom or text-resize run. No screen-reader speech,
real touch hardware, mobile browser, user study, contrast manual review,
comprehension, completion-time, orientation or complete focus-obscuration pass
is claimed. Other checklist states and human evidence remain pending.

## Execution history

Environment: macOS 26.6.2, Node 24.21.0, npm 11.19.0, Playwright 1.64.1,
Chromium 156.0.8078.4, axe-core 4.14.0. Installed the standalone pinned browser
manifest with `npm --prefix tests/browser ci`; no manifest/lockfile changes.
Each run below used `bash scripts/browser-e2e.sh`, including a production build
and the unchanged smoke suite. No full-repository test suite was run.

1. Initial application revision `f5bd781c0c2575b7a23233ffbd09ee4fec4149fa`: **23
   passed, 5 failed** (28 cases, 35.5s browser execution), exit 1. Sign-in,
   roles and readonly profile measured 343px document width at 320px, increasing
   to 370px with text spacing. Consent measured 332px; form cancellation did not
   restore focus to Create role. No new-matrix axe violations; contrast
   incompletes remained.
2. Fast-forwarded to coordinator-requested integration `4e97d2f` (includes
   session navigation and trace changes): **26 passed, 2 failed** (28 cases,
   26.7s), exit 1. Existing shared-header overflow ceased; consent overflow and
   Cancel focus failures persisted. No assertion was disabled or weakened. This
   run began before the final draft-keyboard case and extended geometry
   diagnostics were loaded; the final run below verifies the completed spec.
3. Completed diagnostic spec on the same application revision: **26 passed, 3
   failed** (29 cases, 31.4s), exit 1. The additional failure was a test setup
   error: the new keyboard draft flow omitted required Department and Location
   fields. Corrected the test to enter both through keyboard navigation; this is
   not an application defect or waived check. This run localized consent
   overflow to all four `ConsentDetail` cards
   (`div.rounded-2xl.bg-slate-50.p-5`), whose right edges measured 332px in a
   320px viewport.

4. With required draft fields supplied: **26 passed, 3 failed** (29 cases, 2.4
   minutes), exit 1. Draft creation/extraction succeeded, but the test's first
   generic ARIA `group` selected the job-description details element, not a
   rating fieldset. Narrowed the locator to groups containing radios; the two
   reproduced application findings remained unchanged. This timeout is a
   test-locator defect, not an application keyboard failure.

## Open findings and ownership

| Finding                         | Reproduction / measured result                                                                                                                                                        | File owner / next action                                                                                                                                                                                                                                                                    |
| ------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| A07-R-01: consent narrow reflow | Fresh consent landing at 320×800; document and four detail-card right edges reach 332px, both normally and with text spacing. Main controls remain within horizontal viewport bounds. | Candidate UI: `apps/web/app/candidate/invites/[token]/candidate-assessment.tsx`, consent grid near line 700 and `ConsentDetail` near line 1022. Investigate grid min-content sizing and wrapping; retest 320px with/without spacing. Reflow criterion 1.4.10 review remains open.           |
| A03-F-01: Cancel focus return   | Keyboard open Create role → title receives focus → empty submit returns to title → Tab to Cancel → Space removes form; Create role is not focused afterward.                          | Roles UI: `apps/web/app/roles/roles-workspace.tsx`, `titleInput` focus effect and Cancel handler near line 215. Restore a sensible focus destination and rerun keyboard cancellation; focus-order criterion 2.4.3 review, not an assertion that every focus-return preference is normative. |

Both findings remain failing assertions. Neither is accepted or waived. The
three initial shared-header overflow failures were resolved by coordinator
integration, not by this worker. Contrast incompletes need manual resolution;
zero axe violations do not resolve them.

## Final verified result

Final completed-spec run against application revision
`4e97d2f2628559ba6a3fad2e670c8ee9169ee3b4`: **27 passed, 2 failed, zero
skipped** (29 cases; 28.4s browser execution; runner exit 1). This comprises
**16 passed / 2 failed new accessibility cases** and **all 11 unchanged smoke
cases passed**. The independent keyboard draft test passed, including native
arrow-key radio selection, checked/focused state, nonempty rendered focus-ring
shadow, desktop axe, 320px reflow and reduced motion. The remaining failures are
precisely A07-R-01 and A03-F-01 above. The suite is intentionally red until app
owners fix and retest those findings.

| Stable state       | 320px document width / after spacing | 375px / 1280px reflow | Axe violations  | Contrast incomplete nodes at 320 / 375 / 1280 |
| ------------------ | ------------------------------------ | --------------------- | --------------- | --------------------------------------------- |
| Sign-in            | 320 / 320                            | Pass / pass           | 0 at each width | 3 / 3 / 3                                     |
| Roles list         | 320 / 320                            | Pass / pass           | 0 at each width | 6 / 6 / 6                                     |
| Readonly profile   | 320 / 320                            | Pass / pass           | 0 at each width | 3 / 3 / 3                                     |
| Consent landing    | **332 / 332**                        | Pass / pass           | 0 at each width | 6 / 5 / 5                                     |
| Invalid invitation | 320 / 320                            | Pass / pass           | 0 at each width | 0 / 0 / 0                                     |

All 15 stable-state motion checks passed both initial and changed preference.
Sign-in error-state axe had zero violations and three contrast incomplete nodes;
editable draft desktop axe had zero violations and four contrast incomplete
nodes. Draft document width was 320px at 320px with zero clipped controls. The
raw 1×1 radio input boxes belong to visually hidden inputs with visible label
targets; they are geometry evidence, not automatically failed touch criteria.
Axe spacing/name checks passed only in the scanned states; real touch and focus
visibility/contrast judgments remain outstanding.

Formatting (`prettier --check` on the two owned files) and `git diff --check`
passed. The production build's generated `next-env.d.ts` path change was
restored, leaving only the two owned files for commit. Each runner removed its
own temporary browser artifacts, servers, containers and volumes after failure;
the assigned five ports were verified free after the final run. No screenshots,
trace, raw exports, tokens, mail bodies or browser state are committed. This
report is the durable sanitized evidence; temporary console logs are not part of
the deliverable.
