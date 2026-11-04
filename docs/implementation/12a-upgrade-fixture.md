# 12A populated-upgrade fixture safety

The assignment upgrade fixture accepts only an explicit `TEST_POSTGRES_URL`
using `postgresql+psycopg`, a numeric loopback address, and one of these exact
port/database pairs:

| Port | Database |
| --- | --- |
| 5550 | `iopsych_6c` |
| 5571 | `iopsych_regression` |

Validation happens before engine creation. Hostnames (including `localhost`),
remote addresses, socket paths, missing hosts, scoped IPv6 addresses, other
drivers, missing/default ports, port 5432, cross-paired database names, and all
supplied URL query strings/options are rejected. URL fragments are also rejected.
This prevents query parameters such as `host`, `hostaddr`, `service`, `port`, or
`options` from overriding the approved target or selecting an existing schema.

Each invocation creates a new `assignment_upgrade_<uuid4 hex>` schema using
`CREATE SCHEMA` without replacement. Only the fixture injects a search-path
option, pointing at that generated schema. Cleanup drops only that same schema;
there is no reset of an existing schema or database. The SQLite branch continues
to use pytest's temporary directory. An unset PostgreSQL URL still skips that
fixture variant.

## Connection-free evidence

Run from the repository root:

```sh
.venv/bin/python -m pytest -c apps/api/pyproject.toml apps/api/tests/test_assignment_upgrade_guards.py --no-cov -q
.venv/bin/ruff check apps/api/tests/test_assignment_upgrade.py apps/api/tests/test_assignment_upgrade_guards.py
.venv/bin/ruff format --check apps/api/tests/test_assignment_upgrade.py apps/api/tests/test_assignment_upgrade_guards.py
```

Result: 37 guard tests passed. Tests cover both approved pairs on numeric IPv4
and IPv6 loopback, refusal before engine creation, and a mocked engine verifying
UUID schema creation, generated search path, matching cleanup, and disposal.
No PostgreSQL connection was made by this worker. Actual populated-upgrade
execution on port 5571 belongs to regression dispatch `ctx_38a566c6a71b`;
these unit checks do not claim live database or full regression acceptance.
