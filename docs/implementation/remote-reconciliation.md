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

Validation in progress: npm audit zero vulnerabilities; application/shared Python
mypy passes 82 source files; targeted provider compatibility tests pass (8).
Full merged auth/invitation/report checks, PostgreSQL populated upgrade, and build
are pending the notice and web compatibility checkpoints. Test PostgreSQL is
isolated on loopback port 5606, database `iopsych_reconcile`.
