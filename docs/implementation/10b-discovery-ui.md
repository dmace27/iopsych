# 10B bounded privacy discovery UI

Implemented 2026-11-04 for dispatch `ctx_bbec55d954ea`. This is the engineering
lookup slice of 10B, not full policy/provisioning acceptance. Scope follows
[the implementation plan](../../final-implementation-plan.md),
[specification](../../mvp-spec.md), [finish checklist](../../finish.md), and
[10A contract inventory](10a-contract.md). Read `apps/web/AGENTS.md` and the
installed Next `use-client` guide; retained the existing client boundary.

## Delivered behavior

The existing admin gate runs before privacy requests. Admins can search by one
invitation UUID or role UUID, review assessment IDs and lifecycle timestamps,
and explicitly select an assessment for the existing JSON export, anonymization,
and assessment audit-history workflow. Direct assessment entry remains
supported. Lookup does not expose names or email addresses.

The UI requests 20 results per page, replaces the visible page on Next, and
preserves the reference with the server's opaque cursor. Changing references
clears results and selection. New lookups and target changes clear old exports,
delete results, and pending confirmations. Inputs are locked during requests;
loading, empty, expired-session, and API-error states are explicit.
Anonymization still requires confirmation, now names the target ID, and has a
cancel action. Exports retain the existing JSON download response and
anonymization retains existing policy semantics. No browser storage is used for
discovery or exports.

## Wire contract and integration boundary

`getPrivacyAssessments` calls the same-origin
`GET /api/internal/privacy/assessments`, forwarding to the agreed backend
`GET /v1/privacy/assessments`. Exactly one `invitation_id` or `role_id` UUID is
required. Optional `limit` is 1–50 (server default 20); optional opaque `cursor`
is at most 104 characters. The client validates inputs and URL-encodes cursors.

Strict response schema:
`{schema_version:"1.0", items:[{assessment_id, created_at, submitted_at, retention_expires_at, anonymized_at}], next_cursor}`.
Dates other than `created_at` can be null; `next_cursor` is null or a bounded
string. At most 50 items are accepted. Extra fields (including identity fields)
and malformed lifecycle dates fail response validation. Existing privacy
response schemas are unchanged.

Backend authorization remains ADMIN only, foreign/missing references return
empty 200, and error codes remain `invalid_privacy_cursor` or
`invalid_privacy_lookup` for the agreed 422 cases. Backend fixtures from
`iopsych-privacy-discovery/apps/api/tests/fixtures/privacy_discovery/page.json`
and `empty.json` were inspected; the exact page/empty shapes are exercised in
client contract tests. Backend ownership is dispatch `ctx_546de85cffb9`.

The coordinator must integrate the GET route into the internal proxy allowlist;
this worker did not edit the proxy, backend, migrations, or dependencies.

## Verification

From `apps/web`:

- `../../node_modules/.bin/vitest run lib/privacy-contracts.test.ts lib/api-client.test.ts app/privacy/privacy-workspace.test.tsx`
- `../../node_modules/.bin/eslint lib/privacy-contracts.ts lib/privacy-contracts.test.ts lib/api-client.ts lib/api-client.test.ts app/privacy/privacy-workspace.tsx app/privacy/privacy-workspace.test.tsx`

From repository root: `npm run typecheck --workspace @iopsych/web`.

Result: **24 tests passed across 3 files; targeted ESLint and TypeScript checks
passed.** `git diff --check` also passed.

Tests cover admin gating, exact paths/encoding, backend fixture wire shapes,
strict response bounds, one-reference validation, selection-to-export,
confirmation cancellation/reset, no browser-storage writes, loading, session
errors, empty pages, pagination/filter retention, and error retry. Existing
export/deletion/audit tests remain in the targeted run. No server ports, real
mail, real participant data, deployment, or browser/database E2E were used.

## Remaining package work

Full 10B policy, verified contacts, administrator provisioning, identity
verification, correction/withdrawal procedures, broader candidate discovery, and
related-event audit traversal are pending. This UI preserves existing
assessment-only audit lookup and does not invent a new rights policy. Final
proxy/backend integration and combined browser validation belong to the
coordinator; this slice alone does not authorize real-candidate use.
