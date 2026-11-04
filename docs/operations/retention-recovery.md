# Retention, backup and restore with deletion replay

Privacy administrator, privacy/legal reviewer and recovery engineer:
owner-unassigned. Current cleanup is executable; unattended scheduling/full
lifecycle coverage is gated on 10A/10C and 11A–C. Policy duration, backup
retention, storage location, encryption/key custody, RTO and RPO remain
unapproved/unassigned. Code defaults are not policy decisions.

## Current retention behavior and bounded execution

`PRIVACY_RETENTION_DAYS` defaults to 90 (accepted range 1–3650);
`PRIVACY_RETENTION_BATCH_SIZE` defaults to 100 (range 1–1000). The service
selects non-anonymized **submitted** assessments due by stored deadline, or
derives a legacy deadline from submission time and configured duration. It locks
assessment rows with `skip_locked`, processes at most one batch, and commits.
Changing the current duration does not rewrite existing stored deadlines.

With a verified isolated synthetic database target, this existing root command
performs one **cross-organization** batch:

```sh
npm run privacy:retention
```

The CLI prints only the count anonymized and exits. It has no dry-run mode,
scheduling, durable missed-run signal or automatic backlog drain. The
administrator's `POST /v1/privacy/retention/run` runs one tenant-scoped batch;
`GET /v1/privacy/status` exposes tenant counts/deadlines. Do not confuse the
CLI's scope with the endpoint's scope.

Synthetic operator procedure:

1. Verify target database/organization, configured test policy and synthetic
   due/not-due fixtures. Record pre-run due count through the authorized admin
   status view; distinguish submitted records from lifecycle categories the
   current implementation does not clean.
2. Run one batch, record exit code, count and UTC times without payloads.
   Inspect audit evidence and expected anonymization effects from the rights
   runbook.
3. Recheck due count. For a controlled backlog, run additional bounded batches
   only while counts make expected progress and the authorized rehearsal window
   allows. Stop on errors, unexpected changes or repeated no progress; zero
   processed can mean concurrent locks, not proof the backlog is empty. Record
   due remainder explicitly.
4. Verify not-due fixtures unchanged, repeated cleanup idempotent and
   reports/links for anonymized assessments inaccessible. Do not claim
   unopened/declined/revoked/unsubmitted coverage from submitted-only success.

10C must deliver an unattended scheduler, overlap/concurrency policy, bounded
backlog draining, per-run evidence, failure/missed-run/overdue alerts and all
approved lifecycle deadlines. 11C must deliver actual alert receipt evidence. A
successful manual batch does not close those gates. The currently retained
in-database `candidate_data.anonymized` event is not an external replay
mechanism: an earlier backup may not contain it.

## Backup and restore procedure (gated, not executed)

No repository backup/restore/replay command exists at the inspected revision.
Use 11C's reviewed provider-neutral recovery procedure and 11A deployment
boundary when implemented; do not invent `pg_restore` flags or assume a backup
is complete because its job returned success.

1. Recovery owner records source database identity, backup ID/time,
   schema/release compatibility, encryption/key version, checksum/integrity
   evidence and access controls. Privacy owner approves backup expiry and
   treatment of deletion requests. Record actual recovery objectives only after
   owners supply them.
2. Take an encrypted backup through the approved mechanism. Preserve the durable
   deletion/tombstone journal outside the snapshot rollback boundary under
   approved access/retention controls. 10C must define journal content,
   completeness and replay ordering; this preparation introduces no schema or
   journal contract.
3. For rehearsal, create a synthetic record, take a backup, then anonymize it
   and capture the post-backup deletion evidence. Retain a second non-deleted
   synthetic control. Exercise more than one cleanup batch and idempotent
   deletion.
4. Restore into a newly allocated isolated target, never over an existing
   database. Keep ingress, outbound mail/extraction, candidate access and
   background jobs disabled. Verify backup integrity, migrations, tenant
   isolation, historical report compatibility and audit protections before use.
5. Reconcile deletion events newer than the backup through a documented recovery
   cutoff with the authoritative journal, including requests during recovery.
   Replay all required deletions idempotently before exposing any candidate
   data. Verify deleted payloads/reports cannot be exported/read, tokens are
   invalid and the non-deleted control remains valid. Backup-local audits alone
   cannot prove completeness.
6. Missing/unreadable journal, unknown cutoff, missing decrypt key, replay
   failure or any resurrected record means **stop: keep the restored database
   quarantined**. Do not resume from a partial replay or infer that running the
   submitted-only retention command closes the gap.
7. Record restore and replay timings, recovery point, actual data-loss interval,
   checks and sanitized artifacts. Compare with the approved RTO/RPO only when
   defined. Release/incident and privacy owners must authorize reopening after
   complete reconciliation. Track disposal of rehearsal backups/exports under
   the approved policy; do not reset shared databases.

Required evidence: encrypted backup/integrity verification, successful isolated
restore, old-versus-new schema compatibility, post-backup deletion replay,
duplicate replay safety, no resurrection, intact unaffected control, alert
receipt, measured recovery and recorded owner decisions. All remain pending in
this preparation.
