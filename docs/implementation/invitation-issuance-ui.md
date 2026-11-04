# Invitation issuance UI slice

Implemented from `995cf3c`, preserving the list/revoke focus behavior from
`0a676d6`. Read the web AGENTS instructions, installed Next use-client guide,
implementation plan, existing invitation schemas and profile contracts.

The dedicated form loads existing role profiles and offers approved versions
only. It collects recipient email and optional integer expiry (1–720 hours),
previews those facts, and requires explicit confirmation. Archived roles do not
offer issuance; the server remains authoritative for authorization, approval,
expiry policy and scientific definition eligibility. No consent or purpose text
is invented, and no backend policy, models, dependencies or proxy files changed.

The dedicated client posts strict JSON to
`/api/internal/roles/{roleId}/invites` with `Accept: application/json`,
`Content-Type: application/json`, `Idempotency-Key`, and `cache: no-store`.
The proxy owner must map this to `POST /v1/roles/{role_id}/invites`, forward the
key unchanged, and preserve origin/access protections. The expected response is
HTTP 201 with the existing strict invitation representation. These exact
requirements were sent to the coordinator before implementation.

A random UUID key remains in component memory across uncertain retries and
history refreshes. Payload edits or an explicit new invitation reset it. No
local storage, tokens, links, telemetry or raw upstream errors are used. Leaving
the workspace discards this in-memory state; this UI does not promise exactly
once issuance or backend idempotency in the legacy path. Pending delivery and
active responses are described as stored states, not confirmed receipt.

Synchronous locking prevents duplicate submits. Issuance and existing history
actions disable each other while pending. Success refreshes history while
retaining the result and disabled confirmation; a failed history refresh can be
retried without issuing again. The existing focus destinations, restoration
logic and revoke/pagination handlers remain intact.

## Verification

- Targeted Vitest: **46 passed across 4 files**: issuance client, form,
  issuance integration, and the existing 22-case workspace focus suite.
- Coverage includes strict payload/expiry boundaries, safe failures, HTTP 201,
  token-bearing response rejection, approved-only options, explicit confirmation,
  duplicate-click locking, retry key stability, payload/new-request key reset,
  history refresh retention, access denial, archived/manager gating, profile
  loading retry, stale completion after unmount, and pending action exclusion.
- Scoped ESLint passed with zero warnings; workspace Next typegen and TypeScript
  passed. Generated next-env changes were restored. Prettier and diff checks
  passed.
- All recipients were `synthetic@example.invalid`; all network calls were
  mocked. No servers, ports, database, real mail, secrets, push or deployment.

Coordinator integration with the separately owned POST proxy and queue runtime,
real browser accessibility/focus checks, and full 8B provider/manager product
gates remain pending. This slice does not establish staging delivery acceptance.
