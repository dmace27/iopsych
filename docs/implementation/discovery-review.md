# Discovery integration review

Reviewed 2026-11-04 in isolated worker branch
`AbhiNutakki/iopsych-discovery-review`. Application baseline:
`c060fec3606af7ce57a045698a1ddd75223122a5` after an authorized fast-forward for
the privacy UI handoff. Scope: invitation UI/client/proxy `82d6687`, privacy
lookup backend `9c8783b`, restore rehearsal `9de7fd4`, actual session navigation
`0d31bd0`, and handed-off privacy UI/proxy `39d0d72`/`c060fec`. Only this report
is changed. No application changes, original test changes, services, Docker
mutations, existing databases, mail, deployments, or external providers were
used. This is correctness review, not product/scientific approval.

## Actionable findings

### DR-01 — P2: privacy discovery retains false lifecycle state after mutations

Locations: `apps/web/app/privacy/privacy-workspace.tsx:192`, `:196`, `:212`
(mutation completion) and `:448` (rendering the retained lifecycle data).

Reproduce with synthetic administrator fixtures:

1. Find an invitation whose assessment has `anonymized_at: null` and select it.
2. Prepare and confirm anonymization; return a successful response with that
   assessment ID and a non-null anonymization timestamp.
3. Let the subsequent status/audit refresh finish.
4. The UI simultaneously reports successful anonymization and retains
   **Anonymized: No** in the discovery card. `getPrivacyAssessments` was called
   only once, before the mutation.

The same defect reproduces after **Run retention now** returns the displayed
assessment ID in `anonymized_assessment_ids`. `load()` updates workspace status
and audit history, but neither mutation updates or invalidates `lookupResult`.
The card can therefore mislead an administrator about whether the data-rights
operation completed; backend anonymization itself is not shown to fail.

Fix ownership: privacy UI. Invalidate/refetch discovery on successful deletion
and retention, or reconcile affected rows from authoritative mutation responses.
Preserve a clear success acknowledgement. Regression assertions should require
that a known-anonymized assessment is no longer displayed as not anonymized
following either operation; include a mutation that affects another row on the
same discovery page.

Evidence: two additional external temporary Vitest cases, one per mutation,
executed the real component with synthetic API mocks and asserted the observed
bad state and exactly one discovery request. Both reproduced. Existing privacy
component tests were copied unchanged into that external harness (imports alone
resolved to absolute workspace paths); all 8 existing cases also passed.

### DR-02 — P2: invitation actions remove keyboard focus without a destination

Locations: `apps/web/app/roles/[roleId]/invites/invitation-workspace.tsx:119`
through `:133`, `:231` through `:240`, and `:245` through `:253`.

Two deterministic component repros:

- Focus **Revoke invitation**, press Enter, accept confirmation, and resolve a
  revoked invitation response. The focused button is removed; after the
  **Revoked** status renders, `document.activeElement === document.body`.
- Focus **Load more invitations**, press Enter, and resolve a page with a new
  invitation and `next_cursor: null`. The button disappears and focus again
  becomes the document body.

The live announcement reports the operation but does not preserve a keyboard
navigation destination. On long histories this loses the user's position. Fix
ownership: invitation UI. Explicitly focus a stable status/card destination
following revocation and a sensible new-row/list destination when pagination
removes its trigger; ensure focus remains visible and destination semantics are
announced. Add assertions against the chosen destination, rather than merely
checking the changed text. This is a concrete focus-loss finding, not a claim
that a particular focus policy is mandated by an accessibility standard.

Evidence: two external temporary Vitest/jsdom cases using Testing Library
`user.keyboard("{Enter}")`, real component rendering, synthetic API responses,
and a stubbed native confirmation. Both reproduced body focus. All 11 existing
invitation component cases also passed in the harness. Native browser focus
behavior and assistive-technology announcements still need owner verification.

## Targeted verification and boundaries

- Invitation client/proxy: **11 passed** across the two existing files,
  including upstream errors, schema validation, cursor transport, permission
  failures and cross-origin mutation protection.
- Invitation component external harness: **13 passed**, comprising 11 existing
  tests plus 2 assertions demonstrating DR-02. Existing tests cover role switch
  stale responses, duplicate-request locking, invalid-cursor restart,
  cancellation, retry confirmation, and permission denial.
- Privacy component external harness: **10 passed**, comprising 8 existing tests
  plus 2 assertions demonstrating DR-01. Existing tests exercise selection and
  reference resets, confirmation clearing, export clearing, lookup locks and
  bounded page replacement. Passing defect-reproduction assertions mean the
  defects are confirmed, not fixed or waived.
- Targeted `safe-return-to`, privacy contracts, API client and internal proxy
  tests filtered by `privacy|preserves|rejects`: **53 passed / 14 excluded by
  the filter**, four files. Invitation return paths are already supported by
  `0d31bd0`; this review does not report the superseded navigation issue.
- `pytest apps/api/tests/test_privacy_discovery.py -q`: **18 tests passed** on
  newly created in-memory SQLite fixtures. The command still failed the existing
  global 100% coverage gate (61.28% aggregate on this selected subset); no gate
  was changed and no full-suite success is claimed. Discovery module coverage
  was 100%. Cases cover tenant/role permissions, unknown/foreign selectors,
  minimal projected fields, bounded page sizes, UUID ties, cursor scope,
  canonical encoding, tampering, deleted anchors and anonymized rows.
- Restore script `--self-test`: **8 checks passed**, no Docker mutation. Read
  inspection confirms fresh random ownership labels, explicit local socket,
  target/environment guards, synthetic credentials, loopback publication, schema
  comparison and the explicit unsafe pre-deletion-restore result. No new
  concrete defect established in this bounded review. Docker failure can prevent
  cleanup as already documented; failure-injection and actual restore reruns
  were not performed. The script hardcodes port 5585, outside this dispatch's
  allocated 3153/8173/5593, so it was not launched.

The temporary harnesses lived outside the repository and introduced no original
suite modifications. No full browser/narrow-reflow matrix or PostgreSQL rerun
was performed. No additional confirmed permission bypass, cursor defect or
cross-role stale-response overwrite was found within these checks. Remaining
work is owner fixes and targeted retests for DR-01/DR-02, plus native browser
focus verification; broader existing acceptance/recovery gates remain unchanged.
