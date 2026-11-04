# Deployment and rollback

Status: command inventory current at `3602cb0`; actual deployment and rollback
rehearsal gated on 11A–C, version compatibility (6C) and release authorization.
Release engineering: owner-unassigned. Use the provider-neutral
`deploy/README.md` runbook supplied by 11A and
`docs/implementation/11a-report.md` for acceptance limitations at the reviewed
integration revision. These paths are the coordinator-confirmed handoff
boundary; their commands are pending until the 11A commit is reviewed and are
not present in this baseline. Do not infer a cloud provider or a deploy command
from this document.

## Prepare the release record

1. Record candidate and previous known-good Git SHAs, image/artifact
   identifiers, schema revision, configuration version identifiers (never
   values), assigned assessment/scoring versions and environment identity.
2. Obtain 11A's exact build/start/migrate/stop/rollback commands and
   compatibility notes. Confirm TLS, private API reachability, least-privilege
   runtime versus migration access, secret injection and loopback-only local
   database binding. Reject default/example secrets and placeholder contacts;
   11B must establish hosted validation and readiness.
3. Verify the release's required 12A/12B evidence and outstanding decision
   gates. Confirm a recoverable backup and deletion replay plan from
   [recovery](retention-recovery.md). No real-pilot seed data or automatic
   synthetic seeding in a hosted migration.
4. Check schema compatibility of both old and new application revisions with
   populated data. Outstanding invitations, drafts, submissions and historical
   reports must remain readable under their original interpretation. An
   unreviewed interpretation change is a stop condition.

## Current command inventory

Run from the repository root, only after environment isolation is independently
verified. Installation belongs to 6A; do not race a concurrent setup process.

```sh
git rev-parse HEAD
npm run build
(cd apps/api && ../../.venv/bin/alembic current)
(cd apps/api && ../../.venv/bin/alembic heads)
# Mutates the selected database; execute only in the explicitly approved target:
npm run db:migrate
# Synthetic fixture operations only, never an automatic release step:
npm run db:seed
npm run db:verify
```

`DATABASE_URL` is read by API tooling and can otherwise fall back to local
configuration/defaults. Inspect target host/port/database without printing
credentials before any mutation. Do not run root `db:up`, `db:down`, reset
commands or migration downgrade against a shared database. Follow 6A's reviewed
setup instructions after integration; do not source `.env` as shell code.

After 11A starts an isolated local API on the reserved port, this existing probe
is safe:

```sh
curl --fail --silent --show-error http://127.0.0.1:8108/health
```

A successful `/health` response proves process liveness only; it does not test
database connectivity, schema readiness, delivery or login. Require 11B's
readiness checks plus an authenticated synthetic tenant check and the
[rehearsal](synthetic-rehearsal.md) before enabling traffic. The existing
`npm run security:smoke` is a production HTTP smoke with synthetic
tokens/schema, not a complete browser/provider journey or actual HTTPS cookie
evidence; execution is deferred to the isolated 12A harness.

## Controlled release sequence (gated)

1. Confirm authorized environment, backup, maintenance/traffic controls and
   release owner. Stop writes and delivery as required by the reviewed migration
   plan using 11A controls.
2. Run the reviewed one-off migration with migration credentials, record exit
   status and resulting Alembic revision, then deploy immutable API/web
   artifacts with runtime credentials.
3. Verify readiness, static/shared assets, separate internal identities, tenant
   boundaries, consent, report history, rights and alert delivery using
   synthetic data. Confirm no credentials or invitation paths in
   ingress/application telemetry.
4. Enable traffic only after required checks pass and the accountable owner
   records the decision. Record observed results, not a generic “healthy” claim.

## Rollback or forward repair (gated)

On failed migration, loss of tenant isolation/consent/audit, incompatible
historical records, unsafe logging or failed readiness: stop admission and
delivery, retain sanitized evidence, and follow the incident procedure. Do not
retry uncertain invitation sends blindly.

If the previous artifact is proven compatible with the current schema/data, use
11A's reviewed rollback command and repeat readiness and synthetic checks. If
incompatible, keep traffic stopped and use a reviewed forward repair. Never
assume `alembic downgrade` preserves data, restore an old backup over live data,
or roll back deletion records. A restore requires quarantine and deletion replay
before reopening. Record elapsed outage/data-loss observations for later
comparison with owner-approved RTO/RPO; neither objective is defined here.
Restart requires the release/incident owner's explicit recorded decision and all
stop conditions resolved.
