# Evidence templates and axe handoff

Templates only; blank means **not executed**, never pass. Copy a block for each
run/issue/session. Store only sanitized synthetic evidence in this directory. Do
not commit invitation URLs, cookies, tokens, passwords, mail bodies containing
links, browser storage state or raw network traces. Replace token routes with
`/candidate/invites/[token]`; sanitize screenshots before sharing.

## Manual/automatic run

- Run ID/date/tester; commit/build/content version; fixture alias:
- OS/device/browser/version; assistive technology/version/settings:
- Viewport/zoom/text scale/orientation; input mode/reduced-motion setting:
- Checklist screen/state/check IDs; preconditions and exact steps:
- Expected result; actual observation (include actual speech/focus target):
- Method: source inspection / jsdom / browser automation / manual browser /
  human study:
- Result: pass / fail / blocked / not executed / not applicable (reason):
- Sanitized artifact path; issue IDs; retest commit/result:

Use one result per screen-state/check/environment; a single successful consent
page does not pass all candidate states. Explain every not-applicable entry.

## Finding and fix record

- ID/screen/state; source location or rendered selector; reproduction:
- Observed behavior versus expected behavior; applicable WCAG criterion:
- Evidence level: source risk / reproduced browser defect / human observation:
- Severity: blocker (cannot finish/unsafe irreversible action), major (material
  barrier with workaround), minor (limited friction); affected users:
- Proposed fix; owner/package; dependency; acceptance/retest steps:
- Fix revision and verified environments; unresolved limitations:
- Any accepted limitation: accountable owner, actual decision/date/evidence and
  expiry/retest date. Leave unaccepted until recorded; acceptance is not
  conformance.

## Human session and aggregate

- Study/session ID; intended role; consent to study recorded separately:
- Release/fixture; device/assistive tech; tasks attempted/completed/abandoned:
- Consent start/end; first usable block; successful confirmation; elapsed time:
- Interruptions/assistance; raw and adjusted duration with reason:
- Probe ID; de-identified answer; rubric result; unaided/prompted; observer:
- Aggregate: counts by role/cohort, completions/starts, eligible timing n,
  median/range, exclusions, per-probe counts/denominators, misconceptions:
- Limits, fixes, owner review and next round. Do not fill with fabricated data.

## Accepted automatic lane boundary

Coordinator confirmed via Orca on 2026-11-04: **12A owns implementation and
dependencies in `tests/browser` with standalone manifest/lock**. 12B does not
create a runner or change dependency files. This is an agreed handoff, not
implemented/executed coverage at `3602cb0`.

Reuse 12A's production browser lifecycle and synthetic authenticated fixtures.
After a deterministic readiness condition, scan stable screen states from the
checklist, including open evidence dialog and displayed validation errors. Use
axe tags `wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa`, `wcag22aa` supported by the
installed version; record engine/version and selected tags. Record tool
failure/missing fixtures as blocked, never as a zero-violation pass.

Capture violations **and incomplete results needing manual review**, route
alias, state/checklist ID, revision, browser/viewport and sanitized evidence
references. Do not globally suppress a rule to turn the lane green; document any
scoped exception with reason/owner and retain the finding. Proposed disposition:
all violations triaged, blockers fixed/retested, incompletes manually resolved;
coordinator/12A owns the exact CI exit policy. A zero-violation scan establishes
only that run's automatic result, not keyboard, screen-reader or usability
success.
