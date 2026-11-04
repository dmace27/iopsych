# Local synthetic PostgreSQL restore rehearsal

This bounded experiment proves that a snapshot taken **after anonymization**
restores the checked anonymized state. It also deliberately proves that a
snapshot taken **before anonymization resurrects candidate data** and lacks the
later deletion audit event. No deletion replay is implemented or demonstrated.
An earlier backup must remain quarantined until an authoritative external
journal has been reconciled and replayed. This does not close plan packages 10C
or 11C, or authorize real participants. See the broader
[recovery requirements](retention-recovery.md).

## Run boundary and prerequisites

Run from a dedicated clean checkout with no `apps/api/.env`, using an existing
API Python environment with the repository's dependencies already installed.
The script does not install dependencies, pull/build images, start the API/web,
send email, contact providers, or modify application source/schema definitions.
It applies existing migrations only to its freshly created synthetic database.
Missing dependencies or the local image are blockers; do not install them as
part of this rehearsal.

Required: local Docker Desktop `desktop-linux` context with a Unix socket,
an already available `postgres:16-bookworm` image, and free `127.0.0.1:5585`.
No ambient `DATABASE_URL`, `TEST_POSTGRES_URL`, Docker host/context override, or
PostgreSQL target/credential variable is accepted (see the script's guard).
Never supply a real connection string or credential. The fixed password is
public, disposable synthetic fixture configuration, not a deployed secret.

```sh
# PYTHON denotes the path to the already installed API environment's Python.
"$PYTHON" scripts/verification/local_restore_rehearsal.py --self-test
"$PYTHON" -u scripts/verification/local_restore_rehearsal.py \
  --project iopsych-restore-rehearsal
```

The exact `--project` acknowledgement is mandatory. Every run adds a random
suffix and labels its own two containers. The source publishes only localhost
5585; the restore container uses `--network none` with no published port.
Ports 3000, 8001, 8000 and 5432 are untouched, and reserved web/API ports
3145/8165 are not needed. A busy 5585 fails instead of stopping its occupant.

Both PostgreSQL data directories and the snapshot directory are tmpfs. Dumps
travel through process memory into the restore container's tmpfs; they are not
written into the checkout or a host backup directory. Cleanup verifies owner
labels and removes only the exact container IDs this invocation created,
including their anonymous volumes. No shared compose project, database, network
or volume is reset or removed. An uncatchable process termination or Docker
failure can prevent cleanup; inspect the exact run's label and IDs before any
manual cleanup. Do not use a broad prune or project-name deletion command.

## What the script checks

1. Apply all existing Alembic migrations to a fresh PostgreSQL instance and
   seed two synthetic organizations through the application seed function.
   Add two synthetic consented assessments with report/item rows: one to
   anonymize and one control. These are storage fixtures, not scientifically
   validated assessments or a browser/API journey.
2. Take a real custom-format `pg_dump`, copy it to the separate restore
   container, compare SHA256 digests of the transferred bytes, and run
   `pg_restore --exit-on-error` into a newly created database.
3. Invoke the actual `PrivacyService.anonymize` on the deletion fixture; assert
   one report removed and repeat anonymization idempotent. Take and restore a
   second snapshot into another new database.
4. Compare schema-only dumps and Alembic head for each restore. Ignore dump
   comments, random psql restriction directives and blank lines; normalize only
   PostgreSQL's equivalent whole-array versus per-element text casts. A targeted
   guard test verifies that changing a constraint value still differs. This is
   same-revision restore evidence, not an old/new release migration guarantee.
5. Check the post-deletion restored assessment's definition/responses/scores
   tombstones, anonymized timestamp, replaced email/token hash, revoked invite,
   absent report/items and single deletion audit. Attempt an audit UPDATE and
   require the restored immutable-audit trigger to reject it.
6. Check the control remains non-anonymized with its email, response fixture,
   report and item in both restores. Check the pre-deletion restored target
   still has the original identifying/payload state and report and has **no**
   deletion tombstone. Print `EXPECTED UNSAFE`, never a replay-success claim.

## Executed evidence — 2026-11-04 UTC

Application baseline: `cd113de` (existing Alembic head `20261104_0008`).
Executed in child worktree `iopsych-local-restore-rehearsal`, branch
`worker/local-restore-rehearsal`, using the dispatch worktree's existing
`.venv/bin/python`. No dependency or migration files changed.
Local image ID: `sha256:e8a07d2c7579b038938cdba6c539e580e5001caf9ea203d397b5cc83e76bd938`.

Targeted verification passed:

- Built-in eight guard/normalization checks, with no Docker mutation.
- CLI rejection of missing and foreign project acknowledgements (exit 1).
- Ruff check and format check on the single new script.
- Actual PostgreSQL runtime command above, exit 0, with this output after all
  eight migrations applied:

```text
PASS: before_deletion pg_dump/pg_restore, SHA256 transfer, schema and migration 20261104_0008
PASS: after_deletion pg_dump/pg_restore, SHA256 transfer, schema and migration 20261104_0008
PASS: post-deletion payloads, token, email, reports/items, audit tombstone and audit immutability
PASS: unaffected synthetic control preserved in both restores
EXPECTED UNSAFE: pre-deletion restore resurrects data and lacks deletion audit; external replay REQUIRED, NOT implemented or proven
Cleanup: removed only this run's owned containers and tmpfs snapshots
```

Earlier attempts correctly failed on the equivalent PostgreSQL cast-rendering
mismatch, and cleaned up. The final successful run includes the narrowly scoped
normalization and its regression check. A subsequent container inventory found
no rehearsal containers remaining. No full suite was run.

## Remaining recovery gates

The transfer digest checks byte equality only; it is not encrypted backup,
authenticated archive provenance, key custody or durable storage evidence.
There is no hosted RPO/RTO claim, approved retention policy, production restore,
external journal, replay cutoff/completeness guarantee, duplicate replay test,
restored API authorization/export test, or reopening authorization here.
The post-deletion success must never be substituted for the unresolved
pre-deletion recovery path. The coordinator owns any integration, migration or
dependency follow-up, and accountable owners must separately approve policy and
recovery operations.
