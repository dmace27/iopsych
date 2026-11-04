# 12B screen checklist

Prepared 2026-11-04 from `3602cb0`. **Every runtime check below is pending.**
This is a runnable baseline, not a WCAG conformance statement. Record each
screen/state × check × environment in [evidence.md](evidence.md); missing
screens are blocked, never passed. Source inspection is recorded separately in
the [preparation report](../implementation/12b-preparation.md).

## Shared checks: apply to every row below

- **K — Keyboard:** From a fresh navigation, use Tab/Shift+Tab, Enter/Space,
  radio arrow keys and Escape; finish the task without pointer input. Check skip
  link, meaningful order, no trap, and no unexpected action on focus/change.
- **S — Screen reader:** Read title, landmarks/headings, labels, group names,
  checked/disabled state and instructions. Trigger loading, success and errors;
  record actual speech and whether changes are announced once without losing
  place.
- **F — Focus:** Track visible focus after navigation, mutations, errors and
  dialog close; it must remain usable and not be entirely hidden by app content.
- **E — Errors/recovery:** Submit empty/invalid data; simulate a safe failure;
  find the field and correction, preserve valid inputs, retry once, and verify
  success. Check error association as well as announcement; never rely on color.
- **R — Reflow/mobile:** Test 200% text, 400% zoom at 1280px (320 CSS-pixel
  equivalent), text-spacing overrides, 320/375px widths and both orientations.
  Read and operate all content without clipping or unnecessary two-axis
  scrolling.
- **C — Contrast:** Measure rendered text/background and meaningful controls,
  boundaries, selected states and focus indicators, including errors and
  dialogs; record colors, ratio, size/weight and state. Inspect gradients at
  worst position.
- **M — Motion:** Enable OS reduced motion before loading and during use;
  inspect skeletons, progress and hover transitions; ensure useful status
  remains visible.
- **T — Touch:** On real touch hardware check every action, radio label and
  close control for target size/spacing, accidental activation and scroll
  interference. Emulation alone is not a real-device pass.

Use [WCAG 2.2](https://www.w3.org/TR/WCAG22/) as the normative reference.
Principal mappings: K 2.1.1/2.1.2; S 1.3.1/4.1.2/4.1.3; F 2.4.3/2.4.7/2.4.11; E
3.3.1–3.3.4; R 1.3.4/1.4.4/1.4.10/1.4.12; C 1.4.3/1.4.11; T 2.5.8. Minimum text
contrast is 4.5:1 (large text 3:1), relevant non-text contrast 3:1; minimum
targets are 24×24 CSS pixels or meet a documented exception. Reduced-motion
preference is an additional product check; do not mislabel AAA animation
criterion 2.3.3 as AA. Review all other applicable A/AA criteria before a
conformance claim, including accessible authentication, redundant entry and
consistent help.

## Screen/state tasks

All rows require **K S F E R C M T**, even where the emphasis below is narrower.
Use synthetic identities, `.test` email addresses and loopback capture only.

| ID / route or future surface                         | States and exact task                                                                                                                               | Additional observation                                                                                                                                                                              |
| ---------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| A01 `/` and shared header                            | Follow primary navigation and skip link; return from each workspace; inspect loading/error shell.                                                   | Main target receives usable navigation; page title and active destination are understandable; help stays consistent.                                                                                |
| A02 `/sign-in`                                       | Empty, invalid, pending, successful and expired session; sign out/recover when implemented.                                                         | Labels/instructions and invalid-token alert are discoverable; paste works; provider authentication later needs a fresh pass. Never capture credentials.                                             |
| A03 `/roles`                                         | Empty/list/error/retry; open Create role, submit empty then valid synthetic title/JD; cancel and reopen.                                            | Focus enters form and returns sensibly on cancel; long titles wrap; creation is announced; disabled actions remain understandable.                                                                  |
| A04 `/roles/[roleId]`                                | Extract with deterministic fixture; change rating with arrows, confidence and rationale; save; switch historical versions; try failed/stale save.   | Rating legend/scale and evidence belong together; selection/save announcements identify version; read-only/archived state is understandable.                                                        |
| A05 manager review, same role route                  | Approve eligible draft; inspect unauthorized and already-approved states; future submit/request-edits/reject paths.                                 | Confirm target version and result; reason errors have labels; no focus loss when action disappears. Missing handoff states remain blocked on 7C.                                                    |
| A06 invitation UI, future 8B surface                 | Open form; invalid email/expiry, preview, submit, uncertain delivery, duplicate click, status list, revoke/reissue.                                 | Dialog name/initial focus/containment/Escape/return, announced send outcome and status beyond color. Route is not implemented at baseline; never substitute API success.                            |
| A07 `/candidate/invites/[token]` consent             | Read purpose/use/retention/accommodation/rights; accept or decline in separate disposable fixtures; fail consent then retry.                        | No questions before consent; choices equally reachable; next heading announced; expiry and support copy understood. Do not send contact email.                                                      |
| A08 same route, assessment                           | Complete six blocks by keyboard; select most/least same item then correct; omit selection; skip/unskip; previous/next; reload; storage unavailable. | Radio names include statement and direction; group/position and selected value make sense; error focuses useful choice; progress/save speech matches actual persistence.                            |
| A09 same route, review/completion                    | Change a block; return to review; submit once; retry a simulated failure; reload completion.                                                        | Review is reachable before final submission, no score/ranking, completion heading and rights link usable; no stale draft restored.                                                                  |
| A10 same route, unavailable/declined                 | Invalid/expired/revoked link, declined and already-submitted fixtures; follow recovery/support.                                                     | Distinct understandable outcomes without token disclosure; working help destination; no dead-end focus.                                                                                             |
| A11 `/roles/[roleId]/reports`, `/reports/[reportId]` | Empty/list/loading/error; generate/open complete, partially skipped and insufficient-evidence reports; follow interview-guide link.                 | Six separate constructs, textual classifications, uncertainty and warning read in order; long IDs/evidence wrap; generation status announced.                                                       |
| A12 report evidence dialog                           | Open from each card; Tab/Shift+Tab through dialog, read long content, Escape and Close; reopen another card.                                        | Native modal contains focus and hides background from interaction; named by construct; close returns to exact trigger; close stays reachable at zoom/mobile.                                        |
| A13 `/privacy`                                       | Denied/non-admin, loading/error, invalid assessment ID, export, audit pagination, prepare anonymization then confirm on disposable data.            | Inline confirmation discoverable before destructive action; announce results/downloads and pagination; verify error association, keyboard focus and long audit rows. Never anonymize existing data. |

## Planned environment coverage

Record exact versions, not “latest”: desktop Chromium keyboard at 1280×800;
Safari + VoiceOver on macOS; Firefox + NVDA on Windows; iOS Safari + VoiceOver
on real touch hardware; Android Chrome + TalkBack where available. These are
proposed coverage, not an assertion that devices/testers are available.
Prioritize candidate A07–A10 and report dialog A12, then complete all rows; log
gaps explicitly.
