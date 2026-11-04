# Remote lineage bridge: partial engineering receipt

Status: **rollback-only rehearsal; committing bridge NOT implemented or accepted**.
Operational use remains blocked. The user has not confirmed that any remote-lineage
database exists. This work does not authorize inspecting or changing one.

The isolated worker started at canonical `5cde2e7cc9b98fe8bd25bc7e38c91afa7b20090e`.
The live terminal displayed `GPT-6-Astra medium` without Fast; saved setup completed
with marker `60f9156e-b210-414c-aaf0-64f161b520c4:0`. Read the final plan, progress
ledger, remote migration review, canonical assignment/local queue/access/notice/0012
migrations and exact remote migrations. No applicable ancestor/root AGENTS exists;
the repository's web-only AGENTS does not govern these files.

## Artifact and safety boundary

`scripts/verification/remote_lineage_bridge.py` is an experimental library for its
focused tests. Executing it exits nonzero with an explicit blocked message. It has
no stamp command, no version translation, no deployment mode and no acceptance flag.
The experiment verifies its exact synthetic connection URL, opens a savepoint and
**always rolls back**, including after successful equivalence assertions. Do not
remove this rollback to turn the experiment into an operational migration.

The tests create a uniquely named Docker container labeled
`iopsych.owner=remote-lineage-bridge` and `iopsych.synthetic=true`, bind only
`127.0.0.1:5619`, and use database `iopsych_bridge` with fixed synthetic credentials.
They reject ambient database/Docker configuration and an API `.env`, require the
port to be free, never attach to an existing container, and remove their exact new
container and anonymous volumes in `finally`. No existing database is reset.
The Docker image must already be available locally to avoid an implicit pull.

Run from this isolated checkout with setup complete:

```sh
.venv/bin/python -m pytest scripts/verification/test_remote_lineage_bridge.py -q -s
.venv/bin/ruff check scripts/verification/remote_lineage_bridge.py scripts/verification/test_remote_lineage_bridge.py
```

Remote migration bytes are fetched from the **local Git object database**, never
the network, at `646201a58ceaeb679900344319ea95fdb888641e` and checked before execution:

| Remote migration | SHA-256 |
| --- | --- |
| `20261103_0008_active_internal_users.py` | `8a82710dba4f675beeb5bcdddc56ae526e1d9d90166c0bf27de580b9a364893d` |
| `20261103_0009_invitation_delivery.py` | `0b88a6d743708065c1e92a6091b1f63b763c5691104c01c3d88ebc40c08d106e` |

Canonical migration files must equal their bytes at the pinned canonical commit.
The unchanged assignment migration validates its frozen v1 definition checksum.
The archived Git objects must remain available; no alternate legacy Alembic branch
is registered, and no historical revision, model or dependency was edited.

## Demonstrated bounded behavior

Both source fixtures contain two organizations, two users sharing an email with
distinct global subjects, one disabled user, 18 invites, six consent records, six
assessments, six old v1 reports and six item evidence rows. Definition cases include
known v1, unknown definitions and anonymized submissions. Remote0009 additionally
contains 18 provider deliveries covering all nine statuses in both tenants and 18
webhook events, shared request UUIDs across tenants, replacement links, timestamps,
attempt counts, provider IDs and opaque synthetic ciphertext strings.

Within bounded transactional DDL, the candidate obtains an advisory transaction
lock and ACCESS EXCLUSIVE locks on every source table. It rejects an unknown
revision and an unexpected column before mutation. For remote0009 it renames both
tables, their primary-key constraints and the due index before creating the local
queue; this avoids the otherwise colliding primary-key index name. It executes the
exact frozen assignment, local queue and notice migrations, adds only the missing
user version/check, and preserves existing `is_active`. Remote0008 creates the
canonical provider structures through 0012. The renamed event FK resolves to the
provider table in the observed structural comparison.

The test compares every old column/value in every old table, not just row counts,
and checks exact v1 assignments, unknown/anonymized NULL assignments, immutable
assignment writes, disabled users, version=1, empty local queue, NULL historical
notice evidence, cross-tenant subject uniqueness and duplicate provider-event
rejection. Both normal completion and an injected exception after the rename
restore the original schema, all old rows and original Alembic version. Running
the rollback-only experiment again returns the same receipt.

This is **rehearsal repeatability**, not proof of an idempotent committed bridge.
The signature covers observed columns/defaults/nullability, check expressions,
unique keys, primary keys, foreign-key options, index columns/uniqueness, trigger
SQL and function bodies. It is intentionally NOT treated as a complete production
schema verifier: index predicates/expressions/options, trigger enablement, function
security/configuration, non-table objects and other catalog attributes need a
complete reviewed allowlist and adversarial fixtures before version translation.

## Remaining acceptance work

- Complete source/target catalog signatures and independently pinned manifests;
  reject missing/extra/disabled constraints, triggers, functions and partial states.
- Add authenticated provider-envelope fixtures, exhausted retries, consent-decline,
  audit rows, notice evidence, all constraint violations and writer-lock races.
- Test failures at every phase, especially after target verification and at version
  translation, then persist a durable receipt atomically with a verified version
  translation and prove committed-target no-op behavior.
- Review the canonical0012 downgrade guard and bridge downgrade boundary together;
  never route the converged schema through destructive remote downgrades.
- Only after engineering acceptance, obtain any actual remote-database context and
  operational authorization, backup/restore evidence and writer-quiescence plan.

The original implementation task was reported **partial/failed**, rather than publishing an unsafe committing
bridge within the bounded timebox. Coordinator owns integration and further work.

## Verification receipt (synthetic only)

Focused PostgreSQL run: **5 passed**. Ruff and `git diff --check` passed. Repeated
runs produced these deterministic hashes for exact ordered old-row projections:

| Source | Old-row SHA-256 | Observed source schema SHA-256 |
| --- | --- | --- |
| remote0008 | `639a3018879216665e883cce62d09c80293d49d37fcd5d3e007e88c6c1e3d170` | `f9ec3e8e46f3d7bbb38e8c061ec3fffc277ab8accd345e616c7a83318e6f09ac` |
| remote0009 | `b290a1cc14c8de18d40a8ffcd0fb48d82df5be16ff07cf99756980d96f4591bb` | `6ff89690a8608d328714bccf0b7f32fcaf8234fa10ae6fb3e1d9ba8ad097bedd` |

Observed canonical target signature:
`32fe59f7eb4112a07ee2cfa571a38c1aeb8a7ca3a6e8b4bd6324b1645a8e330e`.
These are evidence hashes of this limited comparison, **not production-approved
schema fingerprints**. Every receipt records `version_translated: false`.


## Independent safety review on integration base 1192fa9

The rollback-only source commit is exactly
`977b81eb9d124d23ba2d8b531d01f65326e517d6`, cherry-picked in the child checkout
as `339325f` onto integration base `1192fa9`. The canonical and remote provenance
pins and all evidence hashes above remain unchanged. The earlier live model/setup
receipt belongs to the original worker; this review does not independently attest
to that worker's model settings.

Review confirmed two guard defects: the ambient list omitted `PGHOSTADDR`, which
libpq can use instead of the URL host, and container startup happened before the
cleanup block. The harness now refuses every ambient `PG*` setting and creates
its container before starting it inside the cleanup block. Cleanup targets only
the ID returned by that creation, including when startup fails; disposal cannot
skip container removal. A Docker creation timeout or daemon failure can still
prevent acquiring an ID or completing removal and must not be represented as
successful cleanup. No existing container is selected or reset.

Python single-letter variables were renamed descriptively without changing data
or comparison semantics. The fixed URL still rejects changed hosts, ports,
databases and socket query overrides before opening a savepoint. The Docker
context must still use a Unix socket and the loopback port must be free. These
are trusted local harness guards, not authentication against a malicious Docker
daemon, custom SQLAlchemy creator or callback that deliberately commits.

Independent fresh owned PostgreSQL 16 on loopback port 5619: **18 passed in 7.49s**,
comprising the original five tests (two populated lineage cases and three refusal
checks) plus thirteen guard cases. Added cases cover six ambient settings,
non-Unix Docker endpoints, an occupied port, startup-failure cleanup and four
changed connection targets. Both populated receipts reproduced every row/source/
target hash above with `version_translated: false`, including successful rollback,
injected-failure rollback and repeatability. Ruff and whitespace checks passed;
no full suite or migration acceptance is claimed. This completes the bounded
safety review while the operational bridge remains partial and blocked.
