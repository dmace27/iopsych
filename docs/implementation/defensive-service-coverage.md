# Defensive service coverage receipt

Base: `b22c7aa23d5915a6a0eadb094386fd422ce3d262`, isolated branch
`AbhiNutakki/iopsych-defensive-service-coverage`. Only the new defensive test
file and this receipt changed. Application code and coverage configuration are
unchanged. Read the implementation plan, progress ledger, and frozen
`regression-accounts-queue.md`; no applicable `AGENTS.md` was present in the
workspace ancestry or API subtree. The worker terminal footer showed
`GPT-6-Astra medium fast`.

## Results

The new file has **13 passing cases, zero skips**, including two real PostgreSQL
cases. An independent bounded baseline of eight existing test files passed all
80 tests with zero skips. No full suite was repeated. Ruff lint/format and
focused mypy pass. The new-file run emits one existing Starlette deprecation
warning.

| Frozen gap      | New evidence                                                                                                                                                             |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Accounts 30     | Both non-admin roles receive 403 without database mutation                                                                                                               |
| Accounts 32     | Service limits -1, 0, 101 raise the documented ValueError without mutation                                                                                               |
| Accounts 60     | A stale nonexistent organization receives 401 without mutation                                                                                                           |
| Accounts 104    | Aggregate results None, 0, 1 fail closed with last_active_admin and unchanged users/audits                                                                               |
| Invitations 120 | Missing queue cipher receives 503 on real PostgreSQL before any write or delivery                                                                                        |
| Invitations 230 | Real duplicate token-hash constraint error is re-raised when the new key has no replay; savepoint rollback preserves every existing row and emits no mail                |
| Auth 27→32      | Existing middleware session is yielded unchanged, remains usable, and needs no factory                                                                                   |
| Privacy 295→292 | Current equivalent 340→337 skips recounting an already anonymized selected assessment, makes no additional database changes, and retains exactly one anonymization audit |

Coverage JSON independently confirms all six target lines and both target arcs
execute in the new file alone. The privacy line shift is from intervening
related audit work; tests assert behavior rather than source locations.

| Measured module        | Statements | Missing | Branches | Partial | Combined coverage |
| ---------------------- | ---------- | ------- | -------- | ------- | ----------------- |
| accounts/service.py    | 54         | 2       | 26       | 2       | 95%               |
| auth/dependencies.py   | 49         | 0       | 12       | 0       | 100%              |
| invitations/service.py | 221        | 14      | 52       | 3       | 93%               |
| privacy/service.py     | 130        | 0       | 40       | 0       | 100%              |
| Total                  | 454        | 16      | 130      | 5       | 96%               |

The bounded baseline was 89% with 43 missing statements and 11 partial branches;
it reproduced all requested gaps. Both diagnostic reports explicitly retain the
100% gate and **exit 2**, not acceptance. Combined missing statements are
accounts 68, 70 and invitations 128, 231, 356–361, 372–375, 389–390. Existing
tests outside this bounded selection are needed for those paths; no claim is
made about the canonical suite or frozen historical-fixture failures being
repaired.

## Isolation and fault boundaries

SQLite uses the existing foreign-key-enforcing in-memory fixture. PostgreSQL
uses only a freshly created `postgres:16-bookworm` container named
`defensive-5d1b-postgres`, labeled `orca.dispatch=ctx_5d1b18641bdb`, with tmpfs
data, loopback port 5604, database `iopsych_defensive`, and synthetic
credentials. Each PostgreSQL test creates and drops only its own random schema.
Both opt-in tests actually ran. The owned container was stopped after
verification. No existing database, other port, network mail, provider,
deployment, or main branch changed. Root/API dotenv files were absent; test
processes inherited only PATH/HOME plus the explicitly shown synthetic database
and coverage-file variables.

The admin aggregate guard is normally unreachable after successful locking and
fresh actor/target authorization: both administrators already exist. Its test
delegates all real queries, verifies the actual count is two, and substitutes
only the aggregate result to prove conservative rejection. The retention case
injects a real public anonymization after real selection and before the record
recheck, then verifies the entire database snapshot is unchanged by the repeat
handling. Neither injection claims ordinary PostgreSQL locking allows that race.
The token collision substitutes only token generation; database constraints,
savepoints, replay lookup, cipher, and queue staging all execute normally.

## Exact verification commands

Run from the workspace root with the fresh owned PostgreSQL container running:

```sh
docker run -d --name defensive-5d1b-postgres --label orca.dispatch=ctx_5d1b18641bdb --tmpfs /var/lib/postgresql/data -e POSTGRES_USER=synthetic -e POSTGRES_PASSWORD=synthetic-local-only -e POSTGRES_DB=iopsych_defensive -p 127.0.0.1:5604:5432 postgres:16-bookworm
env -i PATH="$PATH" HOME="$HOME" COVERAGE_FILE=/tmp/defensive-5d1b-baseline.coverage .venv/bin/coverage run --rcfile=apps/api/pyproject.toml --branch --source=apps/api/app -m pytest apps/api/tests/test_accounts.py apps/api/tests/test_authorization.py apps/api/tests/test_invitations.py apps/api/tests/test_privacy.py apps/api/tests/test_privacy_discovery.py apps/api/tests/test_privacy_related_audit.py apps/api/tests/test_invitation_discovery.py apps/api/tests/test_invitation_delivery_visibility.py --no-cov -q
env -i PATH="$PATH" HOME="$HOME" DEFENSIVE_TEST_POSTGRES_URL=postgresql+psycopg://synthetic:synthetic-local-only@127.0.0.1:5604/iopsych_defensive COVERAGE_FILE=/tmp/defensive-5d1b.coverage .venv/bin/coverage run --rcfile=apps/api/pyproject.toml --branch --source=apps/api/app -m pytest apps/api/tests/test_defensive_service_branches.py --no-cov -q
env -i PATH="$PATH" HOME="$HOME" COVERAGE_FILE=/tmp/defensive-5d1b-baseline.coverage .venv/bin/coverage report --rcfile=apps/api/pyproject.toml --include='*/accounts/service.py,*/invitations/service.py,*/auth/dependencies.py,*/privacy/service.py' --fail-under=100
env -i PATH="$PATH" HOME="$HOME" COVERAGE_FILE=/tmp/defensive-5d1b-combined.coverage .venv/bin/coverage combine --keep /tmp/defensive-5d1b-baseline.coverage /tmp/defensive-5d1b.coverage
env -i PATH="$PATH" HOME="$HOME" COVERAGE_FILE=/tmp/defensive-5d1b-combined.coverage .venv/bin/coverage report --rcfile=apps/api/pyproject.toml --include='*/accounts/service.py,*/invitations/service.py,*/auth/dependencies.py,*/privacy/service.py' --fail-under=100
env -i PATH="$PATH" HOME="$HOME" COVERAGE_FILE=/tmp/defensive-5d1b.coverage .venv/bin/coverage json --rcfile=apps/api/pyproject.toml --include='*/accounts/service.py,*/invitations/service.py,*/auth/dependencies.py,*/privacy/service.py' -o /tmp/defensive-5d1b-new.json
.venv/bin/ruff check apps/api/tests/test_defensive_service_branches.py
.venv/bin/ruff format --check apps/api/tests/test_defensive_service_branches.py
env -i PATH="$PATH" HOME="$HOME" MYPYPATH=packages/shared/python .venv/bin/python -m mypy --config-file apps/api/pyproject.toml apps/api/tests/test_defensive_service_branches.py
node_modules/.bin/prettier --check docs/implementation/defensive-service-coverage.md
git diff --check
docker stop defensive-5d1b-postgres
```

`--no-cov` disables only pytest-cov's duplicate collector; the outer coverage
process measures all API application sources with branches and the committed
configuration. The report include filter displays the four requested modules,
without narrowing collection or claiming the filtered result satisfies the full
suite gate. Coverage data/JSON live under `/tmp`; this receipt is durable.

An initial fixture attempt omitted the new synthetic user's required auth
subject (3 failures); that fixture was corrected before the final 13-pass run. A
standalone mypy invocation initially lacked the shared package search path; the
exact final command above resolves it without suppressions. Coordinator
integration and full canonical acceptance remain outside this worker's scope.
