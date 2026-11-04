# DR-02 invitation keyboard focus fix

Implemented on `AbhiNutakki/iopsych-invite-focus` for the invitation workspace
only, following `apps/web/AGENTS.md`, the installed Next client directive guide,
`final-implementation-plan.md`, and the DR-02 discovery finding.

Successful revocation now focuses the updated invitation list item, whose
accessible name includes the email and stored status. Successful final-page
pagination focuses the first newly appended invitation; an empty or
duplicate-only final page focuses the existing visible status announcement
instead. Both programmatic destinations use `tabIndex={-1}` and a local focus
ring, preserving normal tab order. Nonfinal pagination retains its trigger.
Focus restoration runs after the DOM update and does not override focus moved to
another element while the request was pending.

Native confirmation, cancellation, duplicate request locking, duplicate row
filtering, retries, and async generation checks remain intact. No backend,
proxy, shared stylesheet, contract, or migration changes were needed.

## Verification

- `npm exec --workspace @iopsych/web -- vitest run 'app/roles/[roleId]/invites/invitation-workspace.test.tsx'`
  passed: 22 tests in one file, including all 11 existing cases.
- Added keyboard assertions for successful revoke and subsequent Tab navigation,
  final/nonfinal pagination, duplicate rows, empty/duplicate-only final pages,
  failed revoke/page requests, cancellation, intentional focus movement during a
  request, and late revoke/page completion after switching roles.
- Scoped ESLint on the component and its test passed with `--max-warnings=0`.
- Prettier formatted both changed source files. The first targeted run exposed
  an incorrectly shaped parameterized test fixture; correcting the fixture
  produced the passing result above.

All fixtures were synthetic. No full suite, browser runtime, application server,
database, real mail, protected port, deployment, purchase, or push was used.
Browser-owner verification after integration remains required for native focus,
visible focus rings, and assistive-technology announcements; jsdom assertions do
not establish those browser results. The next step is integration and that owned
browser check, not broader invitation functionality.
