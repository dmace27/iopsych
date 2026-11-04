# 8B invitation list and revoke UI slice

Implementation revision: `5a8cbd7d4a71d28877db1f80703ace866e6d7e4d`.

Adds `/roles/{roleId}/invites`, an admin/recruiter-only role workspace link,
strict web invitation contracts, an isolated client, and exact list/revoke proxy
allowlist entries. Shared-file ownership was confirmed by the coordinator before
handoff; edits to the existing workspace are limited to the link and import.
No backend, root dependency, migration, create, delivery, or scientific changes.

## Behavior and compatibility

- Uses integrated `GET /v1/roles/{role_id}/invites?limit=25&cursor=...` and
  existing `POST /v1/roles/{role_id}/invites/{invite_id}/revoke` unchanged.
- Uses the returned cursor exactly; null ends pagination regardless of page
  length. Invalid cursors offer restart; ordinary page failures preserve rows.
- Displays stored pending_delivery/active/consented/declined/revoked/expired
  states, nullable sent/revoked times, expiry and creation dates, and immutable
  profile IDs. Does not synthesize expired, submitted, delivered or bounced
  states. Archived role history remains available.
- Hiring managers do not fetch invitation data or see the role workspace link.
  API 401/403/404 removes visible history/actions, with sign-in recovery for 401.
  The backend remains authoritative for tenant and role authorization.
- Revocation uses native browser confirmation explaining that existing responses
  and reports are not deleted. All non-revoked stored states can be revoked,
  matching the existing API. A synchronous lock prevents duplicate action
  requests; retries require confirmation again and update from the response.
- Errors use fixed safe copy, never upstream detail/instance or field payloads.
  Strict contracts reject extra token/link fields. Requests and proxy responses
  use no-store. No credential persistence, telemetry, or logging is added.
- Per-role keyed state and generation checks ignore stale asynchronous results.

## Exact verification

From `apps/web`:

```sh
../../node_modules/.bin/vitest run lib/invitation-client.test.ts 'app/roles/[roleId]/invites/invitation-workspace.test.tsx' 'app/api/internal/[...path]/invitation-route.test.ts' 'app/api/internal/[...path]/route.test.ts' 'app/roles/[roleId]/role-profile-workspace.test.tsx'
```

**42 passed, 5 files, no skips**. Covers safe errors, strict status/credential
contracts, exact cursor encoding, no-store, list/revoke route boundaries,
unsupported/create route rejection, cross-site revoke rejection, recruiter/admin
and manager behavior, API denials, native confirmation cancellation, duplicate
clicks, retained state after errors, invalid cursor restart, nullable times,
past-expiry truthfulness, archived history, pagination exhaustion, sign-in,
revoke retry, stale role responses, and existing profile/proxy regressions.

```sh
cd apps/web
../../node_modules/.bin/eslint lib/invitation-*.ts 'app/roles/[roleId]/invites/' 'app/api/internal/[...path]/invitation-route.test.ts' 'app/api/internal/[...path]/route.ts' 'app/roles/[roleId]/role-profile-workspace.tsx'
```

Passed. Prettier applied to changed TypeScript/TSX; `git diff --check` passed.

From repository root: `npm run typecheck --workspace @iopsych/web` passed
(`next typegen && tsc --noEmit`). An initial direct `tsc --noEmit` failed because
Next-generated `PageProps` was absent in this fresh worktree; the documented
workspace typecheck generated the types and passed without source changes.

## Partial acceptance and browser handoff

This completes the assigned list/revoke slice only, not full 8B or 8A acceptance.
Create/expiry/purpose/preview, reissue and delivery lifecycle redesign remain
outside this task. Delivery receipt and assessment submission are unavailable in
this discovery contract and explicitly not claimed. No full-suite coverage,
production build, real browser/axe/manual screen-reader, PostgreSQL, provider or
staging acceptance is claimed. No ports, existing database, email, secrets,
purchases, pushes or deployments were used.

Next eligible verification is the coordinator-owned synthetic browser rehearsal:
open a role as recruiter/admin, follow Manage invitations, inspect archived role
history, paginate, cancel then accept native revoke confirmation, and check a
manager has no entry/action. Verify native-dialog keyboard/focus behavior and
responsive layout in the actual browser. Integration and all release/product/
scientific approvals remain with their accountable owners.
