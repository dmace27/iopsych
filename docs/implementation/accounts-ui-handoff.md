# Accounts administration UI handoff

Implemented from baseline `b457baf` for dispatch `ctx_ca40c8181b0a`.

## Delivered

- `/accounts` provides administrator-only discovery of existing organization accounts, 25 rows per page, previous/next navigation, self read-only controls, role changes, deactivation and reactivation.
- Every mutation requires explicit confirmation and carries the displayed positive `expected_version`. Cancel restores focus; results/errors and loaded pages receive focus. Duplicate submissions are locked synchronously.
- Failed or uncertain mutations clear the pending confirmation and disable further edits until an explicit refresh retrieves current values. No blind conflict retry occurs. Session expiry offers a safe `/accounts` sign-in return path.
- Added strict account contracts and a no-store same-origin client with safe fixed error messages. No auth subjects, tokens, browser persistence, provisioning or organization switching are introduced.
- Added exact GET `/accounts/users` and PATCH `/accounts/users/{UUID}` credential-bearing proxy routes; existing CSRF and cookie handling remain authoritative.
- Added `/accounts` to the exact local return-path allowlist and an admin-only Accounts header link, authorized by coordinator message `msg_5cde3cd39856`.

## Contract and compatibility

GET `/v1/accounts/users?limit=25&after={UUID}` returns `{items:[{id,email,name,role,is_active,version}],next_cursor:UUID|null}`. Limit accepts 1–100; each response is checked against the requested bound and duplicate IDs are rejected. PATCH `/v1/accounts/users/{UUID}` sends `{expected_version,role?,is_active?}` with at least one non-null update and validates the returned identity and advanced version. Roles remain admin/recruiter/hiring_manager. Errors distinguish last_active_admin from account_version_conflict; all failures require refresh before another mutation. This is additive and requires no UI migrations or changes to the organization schema.

Read canonical synthetic backend fixtures from `iopsych-access-admin/apps/api/tests/fixtures/accounts/page.json` and `update.json`; the client tests reproduce their exact values. Backend fixture files remain owned by the API worker.

## Verification

- `npx vitest run --config apps/web/vitest.config.ts apps/web/lib/account-client.test.ts apps/web/lib/safe-return-to.test.ts apps/web/app/accounts/accounts-workspace.test.tsx 'apps/web/app/api/internal/[...path]/account-route.test.ts' 'apps/web/app/api/internal/[...path]/route.test.ts' apps/web/app/ui/site-header.test.tsx`: **89 passed, 6 files**.
- `npm run typecheck --workspace @iopsych/web`: passed after Next route type generation. A preliminary bare tsc invocation lacked generated PageProps; the supported workspace command resolves that prerequisite. Generated next-env path changes were restored and excluded from the commit.
- Targeted ESLint across all changed TypeScript/TSX files: passed with zero warnings.
- `git diff --check`: passed.

Only synthetic mocked requests were used; no servers, databases, protected ports, mail, deploys or external publication were used. No full suite was run.

## Remaining acceptance

Coordinator must integrate the backend router and backend commit, then exercise the complete synthetic API/browser flow including tenant boundaries, disabled access, concurrent updates and last-admin invariants. Those remain server-enforced rules; UI hiding is not authorization. Provider selection, provisioning, membership decisions and full 7B product acceptance remain pending. The next eligible work is integrated account-administration verification, not a declaration that 7B is complete.
