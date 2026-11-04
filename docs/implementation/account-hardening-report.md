# Account rollback and PostgreSQL isolation hardening

Base revision: `b70496563b5ec00e68c71264f99bc537dd1f7202`.
Branch: `AbhiNutakki/iopsych-account-hardening`.
Live Orca terminal status was inspected and displayed `GPT-6-Astra medium fast`;
no mode toggle was performed. Read the accelerated schedule and progress ledger;
the only repository AGENTS.md applies to web files, which were not edited.

## Changes and review

Migration 0010 now refuses downgrade if any disabled account exists, preserving
revocation state rather than silently making those identities usable by older
code. PostgreSQL acquires an ACCESS EXCLUSIVE users-table lock before checking,
held through the transactional DDL to exclude a concurrent access-state write.
The migration never reactivates users automatically. Its import ordering is fixed.

The account PostgreSQL fixture requires the exact psycopg driver, loopback host,
allocated port 5594 and database iopsych_access, and rejects all URL query
parameters before engine construction. Seven negative tests cover host,
hostaddr, port, dbname, service, options and repeated-host overrides.

Reviewed service/router behavior: tenant-first serialization, fresh locked actor
authorization, disabled-user rejection, self-mutation rejection, tenant-scoped
targets, version conflicts, last-admin protection and transactional audit writes
are retained. Mounted HTTP tests exercise fresh permissions and audit rollback.
No service/router change was necessary; no shared models, dependencies or main
application files were changed.

## Validation

Created fresh container `iopsych-account-hardening-pg5594` from locally available
`postgres:16-alpine`, binding only 127.0.0.1:5594, with PostgreSQL data on tmpfs
and synthetic credentials. No existing database was used or reset. The owned
container was removed after validation.

Command from apps/api, with ACCOUNT_TEST_POSTGRES_URL pointing only to the above
isolated database:

```sh
../../.venv/bin/pytest --no-cov -q tests/test_accounts.py tests/test_account_contracts.py tests/test_accounts_postgres.py
```

Result: **40 passed, zero skipped**, in 4.87 seconds. These comprise 24 mounted
API/contract checks, seven URL guards and nine real PostgreSQL cases:

- Six concurrency cases: competing admin deactivation/demotion; stale actor
  escalation after deactivation/demotion; competing same-version role/state edits.
- Immutable audit UPDATE/DELETE enforcement.
- Populated single-revision downgrade/re-upgrade preservation and positive version
  database constraint.
- Actual Alembic base-to-0008 setup, populated with an organization and three users
  spanning all internal roles, then 0009 and 0010 upgrades. Original identities
  and timestamps survive and active/version defaults are correct. A disabled
  recruiter makes downgrade to0008 fail, retaining head0010, disabled state and
  version2, and the delivery table. Explicit synthetic reactivation permits
  downgrade to0008 with original rows intact, followed by a successful head upgrade.

Ruff check and format check passed for both changed Python files; git diff check
passed. Focused strict mypy passed for five account source/test files using
`MYPYPATH=packages/shared/python`. The initial root-level mypy invocation lacked
that source path and reported four unresolved shared-contract imports; correcting
the invocation resolved them without code changes.

## Remaining gates

No blockers or test skips remain for this bounded task. No full-suite coverage
claim is made; targeted execution intentionally used --no-cov. Provider login,
provisioning/membership decisions, browser acceptance, hosted rollback and pilot
approvals remain outside this task. No provider approval, deployment, real mail,
push, purchase or production-secret access was inferred or performed.
