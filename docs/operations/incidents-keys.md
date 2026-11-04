# Incidents and key rotation

Incident commander/security responder: owner-unassigned. Deployment controls and
alert routing are gated on 11A/11C; this is an operator procedure, not evidence
that alerting exists.

## Triage and containment

1. Open a restricted incident record with UTC time, release SHA, affected
   environment, symptom, safe error code/status, affected operation and
   aggregate scope. Do not collect authorization headers, cookies, invite URLs,
   raw requests/responses, job descriptions, candidate answers or privacy
   exports.
2. Stop candidate admission/delivery and affected reads/writes through reviewed
   11A controls for suspected cross-tenant access, consent bypass, unauthorized
   report access, credential exposure, resurrection of deleted data or
   scientific/interpretation drift. Preserve data and immutable audits; do not
   reset the database.
3. Check process liveness (`GET /health`), then separately database/schema and
   11B readiness. Check recent release/configuration identifiers, delivery
   failures and retention outcomes. A green liveness probe cannot clear an
   incident.
4. Classify the boundary: authentication/authorization, database/audit,
   invitation delivery, extraction, privacy cleanup or web/runtime. For
   uncertain email acceptance, halt retries and reconcile under the future 8A
   recovery procedure. For extraction failure, retain draft/approval gates;
   never substitute fabricated evidence or bypass validation.
5. Use tenant-scoped audit queries where available; exact entity filters do not
   traverse related records automatically. Keep evidence access restricted and
   redact identifiers from broad notifications. Assign remediation, validation
   and a next update time in the incident record; communication routes/intervals
   await named owners.
6. Restore service only after synthetic reproduction/negative checks pass, the
   privacy impact is assessed by the accountable reviewer where relevant, and
   the incident owner records restart authorization. Record root cause, impact,
   containment, evidence, remaining actions and owners. Notification
   obligations/timing require actual privacy/legal direction; this runbook
   supplies none.

Synthetic alert rehearsal after 11C: induce a controlled dependency failure in
an isolated environment, capture the alert's sanitized content, receipt time and
responder acknowledgement, recover, and verify resolution. No alert-receipt
evidence means the alerting gate remains open.

## Key inventory and effects

| Current setting/boundary                   | Rotation effect and limitation                                                                                                                                                                                                                                                         |
| ------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `AUTH_JWT_SECRET` (HS256 verifier)         | One verification secret; no dual-key overlap. Old JWTs fail after all API processes load the new key. Existing browser cookies still hold old tokens and require reauthentication; changing a secret does not itself clear cookies. Provider login/issuer coordination is gated on 7A. |
| `INVITE_TOKEN_SIGNING_SECRET`              | One signing key; outstanding old invite tokens fail signature verification after reload. Hash-only storage cannot reconstruct raw links. There is no key-ring grace period. Safe discovery/reissue and uncertain-delivery handling require 8A/8B.                                      |
| `DATABASE_URL` database credential         | Reload/restart connection pools with replacement credentials; migration and runtime identities must be handled separately under 11A. Does not intentionally invalidate user sessions/invitations.                                                                                      |
| `ROLE_EXTRACTION_API_KEY`                  | Replace through the chosen secret store and restart affected API processes. Confirm with deterministic fixtures locally; paid/configured provider probes need separate authorization.                                                                                                  |
| Delivery and backup encryption credentials | Provider-specific inventory, overlap/revocation and restore-key retention procedure are blocked on 8A/11C. Never retire a backup decrypt key before approved backup recovery/expiry requirements are resolved.                                                                         |

## Rotation procedure (gated for hosted execution)

1. Record reason (scheduled/compromised), key identifier, affected consumers,
   operator, environment, and rollback constraints without recording key
   material. Inventory all replicas/workers and outstanding
   sessions/invitations. Obtain the applicable owner-approved outage/reissue
   plan; do not promise seamless rotation.
2. Create replacement random material through the approved secret manager. The
   current auth/invite validators require at least 32 bytes; example strings are
   not suitable secrets. Never put secrets in Git, tickets, command-line
   arguments or captured output.
3. Stop affected issuance/access using 11A controls, update all consumers and
   restart/reload to replace in-memory settings. During a compromised-key
   response, do not retain acceptance of the compromised key or revert to it to
   recover access.
4. Test old credentials are rejected and new credentials work using synthetic
   identities/invites. Verify tenant boundaries, expiry, consent and audit
   behavior. In a mixed-replica rollout, keep access stopped until every replica
   consistently rejects old credentials.
5. Revoke superseded provider credentials after validated cutover. Record secret
   version identifiers, deployment SHA, safe rejection/success evidence and
   affected user recovery. Reissue outstanding invitations only through reviewed
   8A lifecycle procedures; do not mass-reissue through the current unconfigured
   adapter.
