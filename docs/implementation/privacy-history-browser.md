# Related privacy history browser verification

## Scope and environment

This targeted synthetic acceptance journey exercises the related audit API and
privacy workspace integrated at `6a84625` (including `a48f755` and `2ec0b57`).
It uses the production Next build, real Chromium, the internal session/proxy,
FastAPI, a fresh PostgreSQL database, and the local capture mailbox. No
acceptance response is mocked. The route guard permits only the owned web
origin.

The coordinator explicitly handed off ports 3116/8116/5556/1136/8136 after the
invitation worker completed cleanup. Protected ports 3000/8001/8000/5432 and
existing databases were not used. Fast mode was verified from the worker's own
terminal preview without toggling it. Browser dependencies were installed
separately with `npm ci --prefix tests/browser` (zero reported vulnerabilities).

The coordinator additionally authorized one minimal foreign-assessment fixture
in `tests/browser/fixtures.py`. The existing seed entry point creates one Beacon
invitation with no usable bearer token, affirmative consent, and a deterministic
assessment scored with the real assignment scorer. No runner, configuration,
credentials, application code, or other fixture behavior was changed.

## Acceptance assertions

- Complete the existing synthetic privacy invitation through actual consent,
  answer entry, submission, and administrator report generation.
- Open the native report evidence dialog by keyboard; verify initial
  close-button focus, Escape dismissal, and focus restoration to the trigger.
- Discover the Alpha assessment by role, select it by keyboard, and verify its
  selected state and assessment input. Fetch related history through the UI and
  verify invitation access, consent, submission, and report-generation events
  with the real entity references. Consent events currently use the invitation
  entity; the test does not invent a separate consent-entity event.
- Create 51 real export audit events through authenticated same-origin POSTs.
  Verify the first 50-event page, keyboard pagination, the retained
  `assessment_id` selector and cursor, appended older consent events, unique
  event IDs, and the complete rendered count against the related API response.
- Verify foreign-role discovery returns the versioned empty envelope, a real
  foreign assessment and an unknown assessment return 404 for related history,
  and the Beacon manager can see the fixture in its own submitted-assessment
  list but receives 403 for related, exact-entity, and organization history. The
  manager privacy page shows the administrator-only denial.
- Anonymize the selected assessment, verify one derived report was deleted, and
  verify the deletion event remains in related history. The deleted report's
  event disappears from related traversal but remains readable by its exact
  entity reference in the same tenant.

## Results

Command: `scripts/browser-e2e.sh privacy-history.spec.ts`.

Final targeted result on November 4, 2026: **1 passed (4.8 seconds)**, no skips,
runner exit 0, production build successful. The owned API/web processes and
PostgreSQL/mailbox containers and network were cleaned up by the runner. The
report-dialog, selected-history, and manager-denial axe scans each reported zero
violations; selected history reported five incomplete `color-contrast` nodes
requiring manual review, while the other two scans had no incompletes.

`git diff --check`, targeted Prettier, and Ruff check/format with the
repository's API configuration also passed. The generated `next-env.d.ts` build
rewrite was restored, leaving no application changes.

Three earlier iterations corrected test setup and expectations: POST requests
needed the proxy's Origin header, and foreign-role discovery returns a versioned
empty 200 response rather than a 404. Those runs were failures, not acceptance
evidence; each owned stack was cleaned up.

## Limits and remaining work

Related traversal resolves **current** assessment/invitation/consent/report
relationships. Deleting the report removes its joinable relationship, although
the immutable report audit event remains. The UI still describes related report
events without explaining this post-deletion limitation. This is not evidence of
durable historical lineage recovery after report deletion; that needs a separate
product/API/UI change if required.

The spec deliberately runs alone on a fresh stack because it consumes the
existing `PRIVACY` invitation also used by other lifecycle specs. It is not a
whole-matrix result. Automated axe checks and native keyboard dialog checks do
not establish full WCAG conformance, manual screen-reader/contrast acceptance,
cross-browser coverage, hosted HTTPS behavior, or real-participant approval.

No migrations, deployment, pushes, purchases, real mail, or existing-database
reset were performed. The next eligible work is review/integration of this
bounded acceptance evidence and any separately scoped durable-lineage/UI-copy
decision; broader phase 12 gates remain open.
