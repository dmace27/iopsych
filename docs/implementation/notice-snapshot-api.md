# Frozen notice API checkpoint

Base integrated: `f2e6329`; consumes the existing pure snapshot module from
`219f1ef`, without duplicating canonicalization or hashing. Runtime preview
confirmed inherited GPT-6-Astra medium fast; no mode was changed. The child
setup terminal emitted its successful setup-complete marker before tests.

## Contract and storage

Candidate GET and consent POST retain the original response keys unless the
request carries exactly `X-IOPsych-Notice-Snapshot: 1`. Opted-in responses add
nullable `notice_sha256` and `notice_history` with values `not_recorded`,
`digest_recorded`, `legacy_unverified`, or `legacy_unknown`. Optional POST
`presented_notice_sha256` accepts lowercase 64-character hexadecimal. A mismatch
returns 409 `notice_review_required` before any decision or consent audit write.
The digest establishes protocol equality, not proof that a human read anything.

Migration `20261104_0011` has parent `20261104_0010` and adds:

- `assessment_invites.notice_snapshot_json`: nullable JSONB on PostgreSQL, JSON on SQLite.
- `assessment_invites.notice_sha256`: nullable VARCHAR(64).
- `assessment_invites.notice_snapshot_origin`: nullable VARCHAR(24).
- `assessment_invites.notice_snapshot_recorded_at`: nullable timezone-aware timestamp.
- `candidate_consents.presented_notice_sha256`: nullable VARCHAR(64).

No old rows are backfilled. All-null/all-present, digest shape, and origin
constraints protect snapshots. Database triggers in migrations and metadata
creation prohibit changes to recorded snapshots and first initialization after
an existing decision. Downgrade locks PostgreSQL tables and refuses to erase
snapshot or presented-digest evidence. SQLite batch migration restores the
existing assignment-immutability trigger.

Issuance freezes the seven existing notice fields plus the configured retention
days. Legacy undecided GET freezes under the invite lock with origin
`first_presented`; missing-digest POST before GET uses `legacy_decision`.
Existing decisions stay snapshot-free with `legacy_unknown`. Configuration
changes cannot change a frozen notice or its submission retention days; existing
assessment deadlines are never rewritten. No notice content, policy defaults,
scientific decisions, or privacy approval changed.

Privacy export adds six fields inside `consent`: `notice_snapshot`,
`notice_sha256`, `notice_snapshot_origin`, `notice_snapshot_recorded_at`,
`presented_notice_sha256`, and `notice_history`. Existing related-audit selection
and tests remain unchanged. Dynamic wire/export fixtures are in
`tests/test_notice_snapshot_api.py`, including exact legacy and opted-in key sets.

## Verification

Focused pytest command from `apps/api`:

```sh
NOTICE_TEST_POSTGRES_URL=postgresql+psycopg://postgres@127.0.0.1:5603/iopsych_notice ../../.venv/bin/pytest --no-cov tests/test_notice_snapshot_api.py tests/test_notice_snapshot_postgres.py tests/test_notice_snapshot.py tests/test_invitations.py tests/test_privacy.py tests/test_privacy_related_audit.py tests/test_database_migrations.py tests/test_reports.py -q
```

The PostgreSQL tests require exactly that synthetic loopback allocation and
create/drop only their own randomly named schemas. The fresh container is
`iopsych-notice-snapshot-pg`; existing databases and protected ports were untouched.
Coverage includes populated prior-0010 upgrade, consent and decline history,
unchanged existing deadline, concurrent first GET, competing decisions, mixed
GET/legacy POST, immutable storage, downgrade refusal, corrupted content,
configuration changes, old clients, export, and candidate response token/email
exclusion. Final result: **105 passed, zero skipped**, one deprecation warning.

Focused mypy passed for 15 source files including both new test modules and
shared Python contracts. Ruff and `git diff --check` passed. The only test
warning is the existing Starlette TestClient/httpx deprecation. An earlier broad
queue run skipped its 38 unrelated opt-in PostgreSQL cases; no queue runtime
coverage is claimed. The exact existing migration trigger-name expectation was
updated with coordinator authorization.

## Remaining gates and handoff

Coordinator integration, client/proxy capability-header integration, remote
reconciliation, full-suite coverage, browser verification, and actual policy or
scientific approval remain separate gates. No frontend, shared dependencies,
main application mounts, reports service, or unrelated audit logic changed.
This bounded checkpoint freezes shared models, migrations, and services for the
remote reconciliation owner; preserve 0011 and allocate subsequent migrations
after it. No push, deployment, real mail, purchases, or existing database resets
were performed.
