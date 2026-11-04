# Local synthetic deletion replay rehearsal

This experiment restores a snapshot taken before a synthetic deletion, then
replays an independently retained tombstone through the existing privacy service.
It demonstrates the bounded local recovery path left open by
[the snapshot rehearsal](local-restore-rehearsal.md). It does not complete plan
10C/11C, approve retention policy, or authorize production recovery or participants.

## Contract and boundary

The coordinator approved this local-only contract on 2026-11-04. The journal is
canonical JSON with exactly these keys:

```json
{
  "version": 1,
  "run_id": "unique identity of this synthetic run",
  "snapshot_sha256": "SHA256 of the pre-deletion dump bytes",
  "entries": [{
    "tenant_id": "synthetic organization UUID",
    "assessment_id": "synthetic assessment UUID",
    "deleted_at": "UTC ISO-8601 deletion timestamp"
  }]
}
```

Version 1 deliberately accepts exactly one tombstone. Tenant/assessment IDs must
parse as UUIDs, timestamps must be UTC, and unknown fields are rejected. No email,
candidate payload, access token, or credential belongs in this journal. The script
holds a SHA256 of the canonical journal separately in process memory, before
writing a mode-0600 file within a private host temporary directory. It verifies
that trusted digest, version, exact keys, run ID and snapshot binding before
restore and again before replay. The journal is outside PostgreSQL and outside
the snapshot; it survives restoring the earlier database but is deleted when
the bounded experiment ends. No journal or candidate payload is printed.

This digest detects alteration relative to this run's trusted process state.
It is not a signature, encryption, durable trusted storage, or production
provenance. Loss of the process loses the independent digest. There is no
production completeness, cutoff, ordering, multi-entry atomicity, crash recovery,
key custody or retention policy claim. Do not use this format as an approved
production deletion journal.

## Run

Use a dedicated worktree with existing API dependencies and no root or API `.env`.
The script imports only helpers from the actual Python
`scripts/verification/local_restore_rehearsal.py`; that script is unchanged.
There is no shell-script dependency. The runtime requires an already present
`postgres:16-bookworm` image and the local Docker Desktop `desktop-linux` Unix
socket. It never pulls, builds, installs, starts app servers, or sends mail.

```sh
.venv/bin/python -m pytest -q scripts/verification/test_local_deletion_replay_rehearsal.py
.venv/bin/python scripts/verification/local_deletion_replay_rehearsal.py \
  --project iopsych-deletion-replay-rehearsal
```

Missing/foreign project acknowledgements, any `PG*` environment variable,
`DATABASE_URL`, `TEST_POSTGRES_URL`, `DOCKER_HOST`, `DOCKER_CONTEXT`, root/API
`.env`, remote Docker endpoints, missing local image, or busy port 5601 fail
closed. There is no caller-supplied database URL or existing database target.
Only a fresh, randomly named, owner-labeled container publishes
`127.0.0.1:5601`; the source and newly created restored database both belong to
it. PostgreSQL and snapshot storage use tmpfs. The public fixed password is
disposable fixture configuration. Ports 3000/8001/8000/5432 remain untouched.

Cleanup verifies the exact created container ID's owner label before removal
and removes its volumes and the temporary host journal. An uncatchable process
termination or Docker failure may prevent cleanup; inspect the exact run's
identity before manual removal. Never prune shared resources.

## Acceptance demonstrated

1. Apply existing migrations to the fresh database, seed synthetic tenants,
   and create deletion/control assessments with report/item rows. Promote only
   these disposable seed users to admin for the authorization fixture.
2. Take a real `pg_dump -Fc` before deletion. Delete through the existing privacy
   service and record its timestamp in the separately retained journal.
3. Copy the earlier dump to tmpfs, verify byte digest, restore into a newly
   created database, and compare normalized schema and migration head. Prove
   candidate data/report have returned and the later deletion audit is absent.
   No app is started against this quarantined database.
4. Reject a foreign actor/tenant combination, a foreign tenant claiming the
   target assessment, and a recruiter role. Use the existing `require_roles`
   authorization function and tenant-scoped `PrivacyService`, with actor state
   read from the disposable database. Assert denied calls leave candidate and
   audit state unchanged. This is direct service/authorization testing, not
   provider login or HTTP authentication evidence.
5. Replay as the tenant admin and repeat the same entry. Require first deletion
   to remove one report and the duplicate to remove zero, return already-deleted,
   preserve the deletion timestamp, and retain exactly one deletion audit.
6. Verify payload tombstones, replaced email/token, revoked invitation, absent
   report/items, original tenant/actor attribution, byte-equal control records,
   unchanged prior audit rows, and restored triggers rejecting both UPDATE and
   DELETE of audit events.

## Execution evidence — 2026-11-04

Baseline `1d269c4`, dedicated `AbhiNutakki/iopsych-deletion-replay` worktree;
live terminal showed `GPT-6-Astra medium fast` without toggling. Existing
`.venv/bin/python` and local Docker image were used. No application, migration,
dependency or original snapshot-script files changed.

Targeted contract/guard tests: **27 passed**, no skips. Ruff lint and format
checks cover the two new Python files. The real PostgreSQL rehearsal passes
all ten existing migrations through `20261104_0010`, with output:

```text
PASS: verified pre-deletion snapshot restores candidate data and report; quarantined
PASS: external journal binding, tenant/role denial, authorized replay and duplicate idempotency
PASS: payload/email/token erasure, revoked invite, reports/items erased, control preserved
PASS: deletion timestamp/actor/tenant audit, prior audits preserved, UPDATE/DELETE rejected
LOCAL ONLY: no production journal durability, encryption, completeness or retention approval
Cleanup: own container/tmpfs snapshots and temporary external journal removed
```

An initial run exposed a harness exception-type mismatch on the expected tenant
denial; it cleaned up and was corrected to catch the application's
`AccessProblemError`. No full suite, browser/HTTP authentication, production
restore, hosted RPO/RTO, journal-encryption/durability, lifecycle-wide replay,
concurrent replay, or policy-approval check was performed. Coordinator integration
and those broader acceptance gates remain separate.
