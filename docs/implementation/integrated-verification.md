# Integrated verification checkpoint

2026-11-04, Standard/default service only. This is technical evidence, not
whole-plan, hosted-provider, scientific, privacy or release approval.

## API: frozen aggregate plus explicit cumulative coverage

Worker `ctx_dccab8fb8843` ran the entire API at `b13e591` with an empty ambient
environment and all PostgreSQL/Mailpit opt-ins: **1187 passed, zero skipped**.
The unchanged 100% gate initially failed at 99.98%, missing one outbox branch.
At `f02405a`, two persisted terminal-state cases were added; running the whole
11-test new module with `--cov-append` passed and reached **100% of 4242
statements and 876 branches**. Application sources are identical between those
revisions. This is cumulative coverage, not a second whole-suite result.
Integrated equivalents are `cc9d378` and `97c09e4`.

Commands from the isolated child `apps/api`:

```sh
../../.venv/bin/python -m pytest --cov-report=json:/tmp/iopsych-coverage-final-aggregate.json
../../.venv/bin/python -m pytest tests/test_reconciled_coverage.py --cov-append --cov-report=json:/tmp/iopsych-coverage-final-cumulative.json
```

Both use `env -i` with explicit PATH/HOME/TMPDIR. The first additionally sets
TEST_POSTGRES_URL, ACCOUNT_TEST_POSTGRES_URL and NOTICE_TEST_POSTGRES_URL to the
owned numeric-loopback PostgreSQL 5620/iopsych_final; readiness uses
5573/iopsych_readiness, local queue 5586/iopsych_delivery, defensive checks
5604/iopsych_defensive, and IOPSYCH_TEST_LOCAL_MAILPIT=1 with 1139/8139.
All five worker-owned containers and their volumes were removed afterwards;
existing databases were not reset. The exact synthetic environment, commands
and results remain locally in `/tmp/iopsych-coverage-final-receipt.json`, with
aggregate/cumulative logs and JSON alongside it. The 204-case focused run
also exercised all six previously skipped checks, with zero skips.

## Independently executed coordinator checks

- At `e3d73a7`, `npm run test:js`: **637 web and 101 shared tests passed**,
  exit 0 with configured coverage gates. Web statements 94.22%, branches
  91.12%, functions 93.17%, lines 96.05%.
- `npm run typecheck`: web/shared checks and **142 Python source files** passed
  after provider UI integration. Earlier full lint passed; final formatting
  passed after README/account-test and PostgreSQL-test whitespace repairs.
- Python shared contracts: **95 passed**, 100% coverage.
- Notice/privacy/CLI checks: **90 passed** before remote integration; expanded
  CLI checks: **68 passed**, scoped strict mypy/Ruff passed (`0792224`).
- Role accessibility repair: first attempt had **4 pass/2 fail** due to
  concatenated accessible text; `c83204d` adds natural whitespace and all
  **6 targeted tests pass**. The initial failed receipt was corrected promptly.
  Actual browser acceptance still requires the retry run; no axe waiver.
- Saved `npm ci && PYTHON_BIN=python3.12 npm run api:install` succeeded after
  remote dependency reconciliation. npm audit reported zero vulnerabilities.
- Fresh installed Python audit initially found two certifi advisories in
  2026.7.22. `616b861` pins 2026.10.23; pip check passes, and a repeated strict
  pip-audit of **52 installed dependencies reports zero known vulnerabilities**.

## Remaining checks and limits

The initial combined browser run was **37 pass/10 fail**, zero skips. Six axe
failures exposed the role-button accessible-name defect; fixture sharing,
selectors and real rate-window pacing were also repaired. The affected 38-case
retry and provider reissue review are pending at this checkpoint; nine earlier
green cases are not silently counted as rerun. Clean API/web images passed at
`5cde2e7` (see packaging-final.md); the patched-certifi API rebuild is separate.
Secret-scan findings are under exact false-positive review, not yet a clean
claim. The remote-lineage bridge remains a rollback-only synthetic rehearsal,
not authorization to migrate a persisted remote database.
