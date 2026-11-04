# Role maintenance browser slice

Implemented the existing PATCH `/v1/roles/{id}` and DELETE `/v1/roles/{id}`
contracts in a dedicated client, validator, and component, with scoped
profile-workspace integration. Recruiters and administrators can edit changed
metadata fields and confirm archival; hiring managers and archived roles remain
read-only. Successful PATCH data comes from the server; archival status changes
only after the server confirms HTTP 204. Errors retain editable input and
explain recovery, including uncertain network outcomes.

The update validator trims text, rejects empty patches, explicit nulls, unknown
fields, blank values, and excessive lengths (160 for title/department/location;
100000 for description). Metadata changes preserve immutable profile versions.
The native archive dialog provides safe initial focus, cancellation, loading
protection, and completion focus; copy distinguishes preserved history and
blocked writes from data deletion. Existing invitation navigation remains
intact. The archived/no-profile workspace no longer exposes profile creation or
extraction.

The existing internal proxy already permits `PATCH /roles/[^/]+` and
`DELETE /roles/[^/]+`, forwards them to `/v1/roles/{id}`, and preserves
DELETE 204. Exact requirements were sent to the coordinator; no proxy, backend,
schema, dependencies, shared API client, manager states, or notes were changed.

Validation:

- `npm run test --workspace @iopsych/web -- --coverage.enabled=false lib/role-maintenance-client.test.ts 'app/roles/[roleId]/role-maintenance.test.tsx' 'app/roles/[roleId]/role-profile-workspace.test.tsx'`:
  32 passed across three files.
- `npm run typecheck --workspace @iopsych/web`: passed, including Next route
  generation.
- Scoped ESLint on all changed TypeScript/TSX: passed.
- `git diff --check`: passed.

An initial focused test invocation enabled repository-wide coverage and
consequently failed unrelated global thresholds despite all selected tests
passing; the corrected targeted invocation above passed. Plain `tsc` initially
lacked generated Next PageProps; the canonical typecheck command generated them
and passed. No server, database, protected port, provider, email, or deployment
was used.

Limits: native dialog focus trapping and Escape behavior rely on the browser
implementation; component tests exercise dialog intent with jsdom method stubs,
not a real-browser accessibility audit. No full-suite coverage or end-to-end
provider journey is claimed. Full 7C remains gated by approved manager product
states, notes decisions, and provider journey acceptance.
