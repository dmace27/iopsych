# Remote reconciliation collision ledger

Child base: `d99c377`. Remote: `origin/codex/fix-security-dependencies` at
`646201a58ceaeb679900344319ea95fdb888641e`. This branch is a review candidate;
the coordinator is the sole final integrator. No hosted deployment, real mail,
real provider request, or scientific approval is implied.

| Collision | Resolution |
| --- | --- |
| Remote identity choice vs prior research | Adopt implemented Auth0, retain explicit local synthetic HMAC mode, fresh database access checks, tenant uniqueness and fail-closed defaults. |
| Provider account provisioning vs existing account access | Preserve `/v1/accounts/users` and its expected-version service. Add `/v1/users` provisioning; its update adapter requires `expected_version`, delegates the same locking/version service, and returns version. Existing UI remains; provisioning is a separate component. |
| Remote account and delivery migrations | Preserve committed integration `20261104_0008`, `0009`, `0010` unchanged and consume notice `0011`; add provider tables in `0012`. Remote `20261103_0008` maps to existing account activation in integration `0010`; remote `20261103_0009` maps to additive provider `0012`. Remote files are excluded from executable lineage. |
| Remote-head populated databases | **Unsupported upgrade path, blocking deployment to any such database.** Existence/history is not confirmed. Do not stamp, merge heads, rename existing tables, or execute this lineage against remote-head data. A separately reviewed bridge and populated rehearsal are required if such databases exist. |
| Two incompatible `invitation_deliveries` models | Keep local table/model unchanged. Remote uses `ProviderInvitationDelivery` / `provider_invitation_deliveries` and `provider_invitation_delivery_events`. Preserve SMTP uncertainty handling and provider bounded retry/idempotency/webhook behavior separately. |
| Two worker modules | Local worker API retained; provider CLI moved to `app.invitations.provider_worker`, selected by `invitations:deliver`. Local CLI remains explicit synthetic-only. |
| Invitation request keys | Retain legacy ASCII `Idempotency-Key` local digests, excluding the new provider-only request field. Provider mode maps header-only keys to a stable tenant-scoped UUID; body UUID remains supported and contradictory dual keys fail. Delivery modes cannot be enabled together. |
| Credential lifetime | Revoke, consent/decline, expiry, and privacy deletion cancel both stores under existing invitation lock ordering. Delivery state never substitutes for invitation consent/link status. |
| Matching defaults vs frozen assignments | Remote Nov 3 direct structure is repository product evidence, not scientific approval. Version-bound v1 replay/readers, immutable definitions, saved trace, and explicit v2 generation coexist; compatibility owner supplies dedicated followup. |
| Dependency/setup drift | Retain stronger Next 16.4.1, Vitest 5.0.3, cryptography 50.0.2 and integration setup/loopback launcher. Add provider dependencies only; regenerate npm lock. |
| Overlapping test names | Preserve local account/invitation suites and provider equivalents in separately named modules; provider tests target provider models and explicit provider mode. |
| UI design | No redesign in reconciliation. Coordinator merges separate visual branches. |

## Verification and handoff

- Aggregate `ad06206` merges coordinator `d7fd9c9` visual/functional work and
  `3768cfe` export/browser compatibility; production build passes.
- API run: **1,163 passed, six explicit optional skips** on isolated PostgreSQL
  5606. It covers Auth0 mocked signatures/protocol, local and provider issuance,
  worker locking, populated upgrades, notices, historical reports and trace.
- The **100% coverage gate remains unmet: 99.72%** (12 statements). It was not
  relaxed. Machine-readable missing-line evidence is in
  [remote-reconciliation-evidence.json](remote-reconciliation-evidence.json).
  The run started before export source changed; final aggregate coverage must
  be rerun by the coordinator's regression owner.
- Before visual integration: **608 web tests and 101 shared tests passed**, with
  all configured web coverage gates passing. Final visual aggregate build passes;
  browser owner has the aggregate checkpoint for visual and live-session checks.
- Provider downgrade followup tests: **5 PostgreSQL tests passed**, including
  pending and terminal evidence retention; `0012` locks both provider tables
  before checking and refuses any populated downgrade.
- All committed integration migrations `0008`–`0010` and notice `0011` match
  their originating commits byte-for-byte. `0012` alone adds provider storage.
- npm audit reports zero vulnerabilities; stronger security pins are preserved.
  Application/shared Python mypy passed (82 source files). Whole-tree mypy found
  local CLI test typing issues assigned separately by the coordinator.
- Optional readiness (3), defensive PostgreSQL (2), and local SMTP (1) checks
  remain for the coordinator's resource-owning regression workers. No real mail
  or provider requests were made; no provider deployment acceptance is claimed.

Remaining work: final aggregate coverage/typecheck/browser gates, provider
status/reissue frontend and proxy wiring, and any required remote-head database
bridge. These are separate coordinator-owned followups. The provider API wire
supports UUID body keys and the preserved header adapter; local queue semantics
are unchanged. Final trace validation also rejects mixed parent/child algorithm
versions while retaining trace contract version 1.

Use the complete final branch head, not individual intermediate merge commits:
notice conflict cleanup is completed in the subsequent compatibility commit.
Auth web provenance is `0588b71` / `edd94ba` / `dea70a5`; backend v2 provenance is
`927910e` / `3782861`. Functional notice, privacy, CLI, defensive and browser/export
checkpoints are recorded in the branch history. Service policy is STANDARD only.
