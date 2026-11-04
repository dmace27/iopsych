# Focused PostgreSQL integration check

Verified application revision: `c78a70cc2786d69476d1055f54f630e1a14a1b9e` (includes upgrade fixture guard correction `6619167`). Worker branch: `AbhiNutakki/iopsych-pg-regression`; dispatch: `ctx_ccb66e632c3c`.

## Outcome and scope

44 passed, zero failures, zero errors, zero skips across four focused test modules. This is local synthetic regression evidence, not package acceptance, a full-suite coverage gate, hosted validation, or independent coordinator acceptance. Application code, tests, dependencies, migrations, and shared contracts were read-only. Only this report changed. No whole-suite, build, or browser run was performed.

Read `final-implementation-plan.md` and `docs/implementation/progress.md`; no applicable ancestor/root AGENTS.md was present (the repository's AGENTS.md is scoped to apps/web). Fast mode was inherited without toggling.

## Isolation

Started two fresh owned containers from the locally available `postgres:16-bookworm` image, with fresh tmpfs storage at `/var/lib/postgresql/data`, no reused volumes or databases, and loopback-only bindings:

| Container | Host target | Container ID |
| --- | --- | --- |
| `iopsych-pgreg-ctxccb66e-5571` | `127.0.0.1:5571/iopsych_regression` | `8d79b76afccc70ea63fc576b478015f14a4e8e21416403caa030d1b76c59b0a9` |
| `iopsych-pgreg-ctxccb66e-5568` | `127.0.0.1:5568/iopsych_privacy_lock` | `bcd0df9f93de61d902066a4d3af15dd47743585bc790e58db3cebeff51dbe26e` |

Image ID: `sha256:e8a07d2c7579b038938cdba6c539e580e5001caf9ea203d397b5cc83e76bd938`; server reported PostgreSQL 16.15 on aarch64 Debian.

Both ports were free before creation and both instances passed `pg_isready`. Containers used the explicit disposable synthetic username/password `synthetic`; no real credentials were accessed. Tests created random per-test schemas and cleaned them up. Post-run SQL on each database returned only `public` among non-system schemas and zero public tables. Both owned containers were removed using `docker rm -f -v`; existing containers remained running. No application servers were started; ports 3000/8000/8001 and unused reservations 3137/8137 were untouched.

## Exact commands and results

Run from `apps/api` using the existing worktree virtual environment (Python 3.12.16, pytest 9.1.1). The explicit addopts retains strict configuration/marker checks while disabling the whole-application coverage requirement for this focused selection; no coverage acceptance is claimed.

```sh
TEST_POSTGRES_URL=postgresql+psycopg://synthetic:synthetic@127.0.0.1:5571/iopsych_regression ../../.venv/bin/python -m pytest tests/test_assignment_upgrade.py tests/test_assignment_upgrade_guards.py tests/test_reports_postgres.py -o addopts='--strict-config --strict-markers' -p no:cacheprovider -vv -ra --junitxml=/tmp/iopsych-pgreg-ctxccb66e-upgrade-reports.xml

TEST_POSTGRES_URL=postgresql+psycopg://synthetic:synthetic@127.0.0.1:5568/iopsych_privacy_lock ../../.venv/bin/python -m pytest tests/test_privacy_export_postgres.py -o addopts='--strict-config --strict-markers' -p no:cacheprovider -vv -ra --junitxml=/tmp/iopsych-pgreg-ctxccb66e-privacy.xml
```

First command: exit 0, **41 passed in 2.84s**. Second command: exit 0, **3 passed, 1 warning in 0.79s**. Both had zero skipped tests. Warning: StarletteDeprecationWarning that using httpx with starlette.testclient is deprecated in favor of httpx2; dependencies were not changed.

Raw stdout/stderr remains locally in `/tmp/iopsych-pgreg-ctxccb66e-upgrade-reports.log` and `/tmp/iopsych-pgreg-ctxccb66e-privacy.log`; corresponding JUnit XML paths are in the commands. The exact collected passing cases are retained below so this report does not depend on temporary artifacts.

## Passing cases

- `tests.test_assignment_upgrade::test_populated_upgrade_preserves_assignments_and_original_interpretation[sqlite]` — passed.
- `tests.test_assignment_upgrade::test_populated_upgrade_preserves_assignments_and_original_interpretation[postgresql]` — passed.
- `tests.test_assignment_upgrade_guards::test_approved_loopback_pairs[5550-iopsych_6c-127.0.0.1]` — passed.
- `tests.test_assignment_upgrade_guards::test_approved_loopback_pairs[5550-iopsych_6c-127.0.0.2]` — passed.
- `tests.test_assignment_upgrade_guards::test_approved_loopback_pairs[5550-iopsych_6c-[::1]]` — passed.
- `tests.test_assignment_upgrade_guards::test_approved_loopback_pairs[5571-iopsych_regression-127.0.0.1]` — passed.
- `tests.test_assignment_upgrade_guards::test_approved_loopback_pairs[5571-iopsych_regression-127.0.0.2]` — passed.
- `tests.test_assignment_upgrade_guards::test_approved_loopback_pairs[5571-iopsych_regression-[::1]]` — passed.
- `tests.test_assignment_upgrade_guards::test_rejected_before_engine_creation[not a URL]` — passed.
- `tests.test_assignment_upgrade_guards::test_rejected_before_engine_creation[sqlite+pysqlite:///:memory:]` — passed.
- `tests.test_assignment_upgrade_guards::test_rejected_before_engine_creation[postgresql://127.0.0.1:5550/iopsych_6c]` — passed.
- `tests.test_assignment_upgrade_guards::test_rejected_before_engine_creation[postgresql+psycopg2://127.0.0.1:5550/iopsych_6c]` — passed.
- `tests.test_assignment_upgrade_guards::test_rejected_before_engine_creation[mysql+psycopg://127.0.0.1:5550/iopsych_6c]` — passed.
- `tests.test_assignment_upgrade_guards::test_rejected_before_engine_creation[postgresql+psycopg://localhost:5550/iopsych_6c]` — passed.
- `tests.test_assignment_upgrade_guards::test_rejected_before_engine_creation[postgresql+psycopg://example.invalid:5550/iopsych_6c]` — passed.
- `tests.test_assignment_upgrade_guards::test_rejected_before_engine_creation[postgresql+psycopg://192.0.2.1:5550/iopsych_6c]` — passed.
- `tests.test_assignment_upgrade_guards::test_rejected_before_engine_creation[postgresql+psycopg://0.0.0.0:5550/iopsych_6c]` — passed.
- `tests.test_assignment_upgrade_guards::test_rejected_before_engine_creation[postgresql+psycopg://[::]:5550/iopsych_6c]` — passed.
- `tests.test_assignment_upgrade_guards::test_rejected_before_engine_creation[postgresql+psycopg://[::ffff:192.0.2.1]:5550/iopsych_6c]` — passed.
- `tests.test_assignment_upgrade_guards::test_rejected_before_engine_creation[postgresql+psycopg://[::1%lo0]:5550/iopsych_6c]` — passed.
- `tests.test_assignment_upgrade_guards::test_rejected_before_engine_creation[postgresql+psycopg://127.1:5550/iopsych_6c]` — passed.
- `tests.test_assignment_upgrade_guards::test_rejected_before_engine_creation[postgresql+psycopg://2130706433:5550/iopsych_6c]` — passed.
- `tests.test_assignment_upgrade_guards::test_rejected_before_engine_creation[postgresql+psycopg://user@/iopsych_6c]` — passed.
- `tests.test_assignment_upgrade_guards::test_rejected_before_engine_creation[postgresql+psycopg:///iopsych_6c?host=/tmp&port=5550]` — passed.
- `tests.test_assignment_upgrade_guards::test_rejected_before_engine_creation[postgresql+psycopg://127.0.0.1:5432/iopsych_6c]` — passed.
- `tests.test_assignment_upgrade_guards::test_rejected_before_engine_creation[postgresql+psycopg://127.0.0.1/iopsych_6c]` — passed.
- `tests.test_assignment_upgrade_guards::test_rejected_before_engine_creation[postgresql+psycopg://127.0.0.1:bad/iopsych_6c]` — passed.
- `tests.test_assignment_upgrade_guards::test_rejected_before_engine_creation[postgresql+psycopg://127.0.0.1:5550/iopsych_regression]` — passed.
- `tests.test_assignment_upgrade_guards::test_rejected_before_engine_creation[postgresql+psycopg://127.0.0.1:5571/iopsych_6c]` — passed.
- `tests.test_assignment_upgrade_guards::test_rejected_before_engine_creation[postgresql+psycopg://127.0.0.1:5571/existing]` — passed.
- `tests.test_assignment_upgrade_guards::test_rejected_before_engine_creation[postgresql+psycopg://127.0.0.1:5550/iopsych_6c?]` — passed.
- `tests.test_assignment_upgrade_guards::test_rejected_before_engine_creation[postgresql+psycopg://127.0.0.1:5550/iopsych_6c?host=remote.invalid]` — passed.
- `tests.test_assignment_upgrade_guards::test_rejected_before_engine_creation[postgresql+psycopg://127.0.0.1:5550/iopsych_6c?host=/tmp]` — passed.
- `tests.test_assignment_upgrade_guards::test_rejected_before_engine_creation[postgresql+psycopg://127.0.0.1:5550/iopsych_6c?hostaddr=192.0.2.1]` — passed.
- `tests.test_assignment_upgrade_guards::test_rejected_before_engine_creation[postgresql+psycopg://127.0.0.1:5550/iopsych_6c?port=5432]` — passed.
- `tests.test_assignment_upgrade_guards::test_rejected_before_engine_creation[postgresql+psycopg://127.0.0.1:5550/iopsych_6c?service=existing]` — passed.
- `tests.test_assignment_upgrade_guards::test_rejected_before_engine_creation[postgresql+psycopg://127.0.0.1:5550/iopsych_6c?options=-csearch_path=public]` — passed.
- `tests.test_assignment_upgrade_guards::test_rejected_before_engine_creation[postgresql+psycopg://127.0.0.1:5550/iopsych_6c?sslmode=disable]` — passed.
- `tests.test_assignment_upgrade_guards::test_generated_schema_only_and_cleanup_without_connection` — passed.
- `tests.test_reports_postgres::test_concurrent_submissions_and_reports_are_single_snapshots` — passed.
- `tests.test_reports_postgres::test_postgres_retention_skips_locked_rows_then_anonymizes_atomically` — passed.
- `tests.test_privacy_export_postgres::test_export_first_materializes_before_erasure_and_commit` — passed.
- `tests.test_privacy_export_postgres::test_erasure_first_waiting_export_rejects_even_preloaded_state` — passed.
- `tests.test_privacy_export_postgres::test_postgres_api_export_preserves_audit_headers_and_tenant_hiding` — passed.

## Interpretation and remaining gates

The populated upgrade ran against both SQLite and actual PostgreSQL and preserved assignments/original interpretation. The 37 guard cases cover six approved loopback pairs, thirty rejected URLs before engine creation, and generated-schema-only cleanup. Actual PostgreSQL report tests exercised concurrent submission/report single snapshots and retention skipping locked rows before atomic anonymization. Privacy tests exercised export first, erasure first with preloaded export state, and API audit/header/tenant-hiding behavior.

No guard blocked the approved targets and no edits were needed to make tests pass. The earlier populated-upgrade target failure did not recur at this revision. This selection does not establish correctness outside the asserted interleavings or substitute for a whole-suite/hosted release gate. Coordinator independent review remains required; no product, scientific, privacy-policy, or deployment acceptance is inferred.

Protected `main` was `f5224c9d7d7d6b143bd43c3ca5c77022856cdb90` before and after the run. The primary checkout `/Users/abhiramnutakki/iopsych` had clean tracked/untracked status before and after the checks. The worker worktree was clean before the report; its only intended change is this report. No push, deployment, purchase, real email, or existing database reset occurred.
