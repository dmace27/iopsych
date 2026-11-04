# 7A session navigation slice

Implemented in dedicated worktree `iopsych-session-navigation`, branch
`AbhiNutakki/iopsych-session-navigation`, from integration baseline `c78a70c`.
This report accompanies the scoped implementation commit; it does not close
provider login or all package 7A acceptance gates.

## Behavior and boundaries

- Internal header loads existing `getCurrentUser`, displays name, permission
  role, and current organization UUID (the existing contract has no organization
  name). The UI does not imply organization switching or add any permission
  authority.
- Account state refreshes on internal pathname navigation, window focus and a
  60-second interval. HTTP 401 provides a visible sign-in recovery link; other
  failures show an account-unavailable message. Pending requests cannot restore
  stale account context after unmount, a newer fetch, or sign-out initiation.
- Visible sign-out calls existing `DELETE /api/session`; only success removes
  the account and navigates to sign-in. HTTP/network failures retain account
  context and announce that the session may still be active, with retry enabled.
- Recovery preserves exact allowlisted paths: `/roles`, `/roles/:uuid`,
  `/roles/:uuid/reports`, `/reports/:uuid`, `/privacy`. UUIDs require canonical
  hexadecimal groups, versions 1–8 and the standard variant. There is no
  `/reports` index page. Everything else falls back to `/roles`, including
  external/protocol-relative/backslash/encoded paths, traversal, whitespace,
  queries, fragments, unknown suffixes and candidate invitation paths.
- Header constructs recovery URLs from pathname only; server page sanitizes
  `returnTo` before client serialization, and form validates again at
  navigation. No token or candidate invite URL is added to recovery links, logs
  or storage. Existing global `Referrer-Policy: no-referrer` is preserved;
  recovery link and sign-out fetch additionally specify no-referrer.
- Candidate routes render no internal account controls/navigation and never
  mount account fetching. Sign-in and unknown public routes do not fetch
  accounts.
- Existing provider-token exchange payloads and synthetic selection are
  unchanged; synthetic login remains explicitly enabled development-only on the
  server page. No API-client, proxy, shared contract, dependency, migration or
  database edits.

## Executed evidence

- `npm exec --workspace @iopsych/web -- vitest run app/ui/site-header.test.tsx app/sign-in/sign-in-form.test.tsx app/sign-in/page.test.tsx lib/safe-return-to.test.ts`
  — **4 files, 61 tests passed**. Mocked synthetic cases cover account identity,
  initial missing auth, expiry on focus, sign-out success/HTTP/network failure,
  candidate isolation and navigation, late completion after unmount, development
  guard, safe return navigation, and malformed/open-redirect inputs.
- `npm run typecheck --workspace @iopsych/web` — passed (`next typegen` and
  `tsc --noEmit`). Restored its generated `next-env.d.ts` change to preserve
  scope.
- Scoped `npm exec --workspace @iopsych/web -- eslint` for all eight
  implementation and test files with `--max-warnings=0` — passed.
- Prettier for all owned implementation/test files and `git diff --check` —
  passed.

No browser suite, server, database, build or external service was started;
reserved ports 3135/8135/5575 and existing 3000/8000/8001 were untouched. No
push, deployment, purchase, real email, secret or real participant data used.

## Remaining integration checks

Browser owner can extend the existing production journey to assert header name,
role and organization; visible sign-out; unauthenticated recovery on a
role-report or report-detail path; safe return after login; and no account
request on candidate pages. Polling detects idle expiry within approximately 60
seconds (or on focus), rather than intercepting other components' API failures.
Provider selection, provider callback/signature integration, organization
display-name enrichment, and full hosted 7A acceptance remain outside this
slice.
