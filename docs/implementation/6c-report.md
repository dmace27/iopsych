# 6C bounded backend compatibility handoff

Date: 2026-11-04. Worker branch: `AbhiNutakki/iopsych-6c-versions`.
Base: `4638236`. The implementing commit contains this report.
**Bounded backend work complete; whole-package acceptance pending 6B decisions,
actual content review and separate frontend integration.**

## Delivered

- Complete immutable invitation assignment snapshots, retained checksum-verified
  draft v1 definition, explicit v1 scoring/matching/report-reader registry.
- Consent-gated assigned-definition endpoint with unchanged strict landing,
  consent, internal invitation and submission response shapes. Exact frontend
  handoff: [6c-contract.md](6c-contract.md).
- Default denial of unreviewed new assignments; explicit
  `INVITE_ALLOW_SYNTHETIC_DEFINITIONS=true` development opt-in. Historical
  assignments remain usable independently of future issuance policy/retirement.
- Single allocated migration `20261104_0008` over `20260929_0007`, frozen migration
  artifact, conservative populated legacy backfill and SQLite/PostgreSQL snapshot
  mutation triggers. Unknown/malformed/anonymized history remains unsupported;
  no assessment/report payload is rewritten and deleted data is not restored.
- Stable unsupported-version errors; report reads use stored v1 result, never
  recompute. Report generation dispatches from the assignment's algorithm.
- Focused registry/API/migration tests; existing synthetic invitation/report and
  one privacy-submission fixture explicitly opt in or construct pinned snapshots.

Coordinator approved the proposed API/storage/backfill/unknown-version/migration
contract through Orca before shared backend edits. Its requested correction was
followed: no additive assignment field on existing strict candidate responses.
No shared TypeScript schema, frontend, auth/startup, root dependency, packaging,
ops, provider, structure interpretation or integration-checkout changes.

## Commands and evidence

All commands ran in this child worktree with synthetic data only.

1. `npm ci && PYTHON_BIN=python3.12 npm run api:install` — exit 0; saved setup
   completed/verified. npm reported 15 dependency advisories (11 moderate,
   3 high, 1 critical) and install-script allowlist warnings; dependencies were
   not changed. No active Git commit hook is configured (sample hooks only).
2. Baseline: `.venv/bin/python -m pytest apps/api/tests/test_invitations.py apps/api/tests/test_reports.py apps/api/tests/test_database_migrations.py --no-cov -q`
   — 30 passed.
3. Isolated PostgreSQL:
   `docker run --detach --name iopsych_6c-postgres --publish 127.0.0.1:5550:5432 --env POSTGRES_DB=iopsych_6c --env POSTGRES_USER=iopsych --env POSTGRES_PASSWORD=iopsych postgres:16-alpine`
   — exit 0. Synthetic local-only credentials; no existing container/database
   reused. Upgrade tests create/drop unique schemas with no public fallback.
4. Final focused backend verification:
   `TEST_POSTGRES_URL=postgresql+psycopg://iopsych:iopsych@127.0.0.1:5550/iopsych_6c .venv/bin/python -m pytest apps/api/tests/test_assignments.py apps/api/tests/test_assignment_upgrade.py apps/api/tests/test_invitations.py apps/api/tests/test_reports.py apps/api/tests/test_reports_postgres.py apps/api/tests/test_database_migrations.py apps/api/tests/test_privacy.py --no-cov -q`
   — **64 passed, zero skips**. Includes populated SQLite/PostgreSQL upgrades,
   downgrade retention, SQL/ORM mutation attempts, legacy response compatibility,
   unchanged stored report interpretation, and existing PostgreSQL concurrent
   submission/report checks. An earlier run found an unassigned privacy fixture;
   corrected with an explicit synthetic snapshot before the passing run.
5. Registry branch coverage:
   `.venv/bin/python -m pytest apps/api/tests/test_assignments.py --override-ini='addopts=--strict-config --strict-markers' --cov=app.assignments --cov-branch --cov-report=term-missing --cov-fail-under=100 -q`
   — **26 passed; 100% statements and branches** (80 statements, 10 branches).
6. Scientific v1 regression:
   `.venv/bin/python -m pytest -c packages/shared/python/pyproject.toml packages/shared/python/tests/test_assessment.py packages/shared/python/tests/test_matching.py --no-cov -q`
   — **78 passed**. The initial invocation omitted `--no-cov`: all 78 passed,
   but the command exited 1 because unrelated shared modules brought aggregate
   coverage to 96% against the full-suite 100% gate. Corrected to the explicitly
   focused invocation above; no scientific test/code changes.
7. `MYPYPATH=packages/shared/python .venv/bin/python -m mypy --config-file apps/api/pyproject.toml apps/api/app/assignments apps/api/app/invitations apps/api/app/reports/service.py apps/api/app/database/models.py apps/api/tests/test_assignments.py apps/api/tests/test_assignment_upgrade.py`
   — success, 15 source files. Initial run without MYPYPATH could not resolve the
   editable shared package; explicit path fixed tool discovery.
8. `.venv/bin/python -m ruff check --fix --config apps/api/pyproject.toml apps/api/app/assignments apps/api/app/invitations/config.py apps/api/app/invitations/router.py apps/api/app/invitations/service.py apps/api/app/reports/service.py apps/api/app/database/models.py apps/api/alembic/versions/20261104_0008_immutable_assignments.py apps/api/tests/test_assignments.py apps/api/tests/test_assignment_upgrade.py apps/api/tests/test_database_migrations.py apps/api/tests/test_invitations.py apps/api/tests/test_reports.py apps/api/tests/test_privacy.py`
   — success after two import-order fixes; the same paths with
   `ruff format --check --config apps/api/pyproject.toml` pass (14 files).
   Explicit config avoids local Alembic namespace inference differing from the
   repository lint command. `git diff --check` — success.

## Limits, callers and next work

No full-repository coverage run, browser tests, real mail, external provider,
public deployment, production secrets, or actual content review were performed.
The web/API servers were not started, and reserved ports 3110/8110 were unused.
Database port 5550 was used exclusively; existing ports/databases were untouched.
The isolated `iopsych_6c-postgres` container is stopped after verification.

Next frontend worker should fetch the assigned definition after consent, render
that response, preserve legacy v1 drafts and handle unsupported versions without
falling back to the current imported definition. The existing static frontend
still renders v1 pending that separate change. Existing browser/scaffold callers
creating synthetic invites must explicitly set the new invitation setting; no
implicit local-host exemption was introduced. No claim is made that device drafts
were tested through a browser: upgrade coverage replays their unchanged v1 payload.

Future reviewed entries require real evidence, an approved definition revision and
eligibility registration. DB owners can bypass triggers; enforcement covers normal
ORM/direct SQL updates, not privileged schema modification. Snapshot JSON is
nullable only to represent unsupported history; new service-issued invites always
pin it. Repair/reassignment of unsupported history requires a separate authorized
migration, never a silent fallback. Real-pilot acceptance, 6B interpretation/privacy
choices and frontend reader integration remain open.
