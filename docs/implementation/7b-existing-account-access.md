# Bounded existing-account access administration

This is a partial engineering delivery for 7B, approved by the coordinator in
`msg_31776cbb77a4` on 2026-11-04. It preserves the existing one-organization
user schema; it does not approve D03, select an identity provider, provision
users, add memberships/switching, send mail, or complete full 7B. Provider and
product choices remain pending.

## Contract and integration

The coordinator must mount `app.accounts.router.router` in `app.main`. The
worker deliberately did not edit main or existing router modules. Canonical
examples are in `apps/api/tests/fixtures/accounts/`.

| Operation                            | Contract                                                                                                                                                |
| ------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `GET /v1/accounts/users`             | Admin only; `limit` defaults to 25 and accepts 1–100; optional `after` UUID must identify an account in the current tenant; UUID ascending keyset order |
| List response                        | `{items: [{id,email,name,role,is_active,version}], next_cursor: UUID or null}`; at most `limit` items; no provider subject                              |
| `PATCH /v1/accounts/users/{user_id}` | Admin only; strict positive integer `expected_version`; non-null `role` and/or strict boolean `is_active`; extra fields rejected                        |
| Mutation response                    | `{id,email,name,role,is_active,version}`; one increment per actual change; a no-op preserves the version                                                |

Successful responses set `Cache-Control: no-store`. Existing problem-detail
handlers render errors: inactive identities get 401 `authentication_required`,
non-admin and self-directed changes get 403 `permission_denied`, unknown or
foreign targets/cursor anchors get 404 `resource_not_found`, stale updates get
409 `account_version_conflict`, and validation errors get 422. The last-admin
guard uses 409 `last_active_admin`. Self-directed changes, including no-ops, are
denied as the approved conservative engineering guard, not a newly approved
product workflow. There is no account creation route or email search.

## Transactions and authorization

Every account mutation locks its organization row first, reloads and locks the
actor with `populate_existing=True`, checks active/admin state, and then reloads
and locks the tenant-scoped target. This serializes all access mutations within
a tenant without ordering actor and target locks against each other. Competing
revocations cannot both succeed: the losing request observes the actor's new
state before it can mutate another account. Parallel demotion cannot authorize a
stale administrator's escalation. The remaining active-admin count is checked
under the same organization lock. With self-mutation forbidden and an active
admin actor required, the explicit last-admin count check is defense in depth.

The request-owned transaction retains locks through commit. A changed account
and `account.access_changed` event commit together; audit failure rolls back the
change. Mutation metadata contains only before/after role, active state, and
version, with actor/target/tenant IDs in ordinary audit columns. Existing audit
middleware separately records discovery and attempted changes, including
rejections/no-ops. Existing database audit immutability protections apply.

Authentication rejects disabled users after valid token verification. Existing
database role resolution remains authoritative on subsequent requests, so a role
change does not require token replacement. This does not promise cancellation of
unrelated requests already authorized before the access change committed. The
account mutation path specifically reauthorizes after its serialization lock.
Out-of-band SQL writers do not participate in the application locking protocol.

## Migration

Allocated revision `20261104_0010_user_access.py` has parent `20261104_0009`. It
adds nonnullable `is_active` with server/Python default true and `version` with
server/Python default 1 plus `ck_users_version_positive`. Existing rows remain
active at version 1; identity, tenant, email, name, role, and timestamps are
preserved. Apply the complete integrated migration chain before starting the
updated application. Downgrade removes access-state/version information; it must
not be treated as a way to retain deactivations on old application code.

The predecessor belongs to the delivery worker. Full migration-chain execution
is pending its handoff; this report does not claim that integration check
passed. This revision's downgrade/upgrade was independently exercised on
populated synthetic PostgreSQL tables and preserved all preexisting identity
values.

## Validation evidence

Fresh owned container `iopsych-access-admin-pg`, PostgreSQL 16, loopback port
5594, database/user `iopsych_access`, synthetic records only. Tests take an
explicit `ACCOUNT_TEST_POSTGRES_URL`, reject other host/port/database targets,
and create/drop randomized isolated schemas. They never fall back to ambient
`DATABASE_URL`. No protected ports, provider calls, existing database, real
mail, pushes, or deployment were used.

Commands (from the worktree root, with the explicit local PostgreSQL URL set):

```sh
.venv/bin/python -m pytest -c apps/api/pyproject.toml \
  apps/api/tests/test_accounts.py apps/api/tests/test_account_contracts.py \
  apps/api/tests/test_accounts_postgres.py apps/api/tests/test_authorization.py \
  apps/api/tests/test_database.py --no-cov -q
.venv/bin/python -m mypy --config-file apps/api/pyproject.toml \
  apps/api/app/accounts apps/api/tests/test_account_contracts.py \
  apps/api/tests/test_accounts.py apps/api/tests/test_accounts_postgres.py \
  packages/shared/python/iopsych_contracts
```

Focused validation: 49 tests passed with no skips, including six PostgreSQL
tests; strict mypy passed for 14 source files; Ruff checks and formatting passed
for changed Python files. Tests cover bounded tenant discovery, foreign/missing
cursor and target parity, strict contracts, non-admin denial despite admin token
claims, version conflicts, fresh role authorization, disabled valid tokens,
reactivation, no-op behavior, self-mutation denial, atomic audit rollback,
concurrent cross-revocation/demotion, stale-actor escalation rejection, database
audit immutability, and populated standalone migration compatibility. This is
focused evidence, not a full-repository or browser acceptance run.

Remaining integration: predecessor 0009 and full migration-chain test;
coordinator-owned main mount; consumer/UI integration and combined regression.
Provisioning, real provider login, membership/product decisions, and full 7B
acceptance remain pending.
