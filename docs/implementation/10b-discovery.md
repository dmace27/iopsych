# 10B: bounded privacy assessment discovery

Engineering contract approved by the coordinator on November 4, 2026. This is an
additive synthetic-data implementation slice, not completion of package 10B or
approval of privacy policy, identity verification, correction, withdrawal,
retention changes, scientific validity, or real candidate use.

## Version 1.0 wire contract

`GET /v1/privacy/assessments` uses the existing internal authentication and
organization-scoped `ADMIN` dependency. Recruiters and hiring managers receive
403; unauthenticated requests receive the existing 401 response.

Query parameters:

| Parameter       | Contract                                                      |
| --------------- | ------------------------------------------------------------- |
| `invitation_id` | Exact invitation UUID; mutually exclusive with `role_id`      |
| `role_id`       | Exact role UUID; mutually exclusive with `invitation_id`      |
| `limit`         | Integer 1–50, default 20                                      |
| `cursor`        | Optional opaque cursor; maximum request length 104 characters |

Exactly one selector is required. Missing/both selectors produce 422
`invalid_privacy_lookup`. Invalid UUIDs, bounds, and overlong cursors produce
existing 422 `request_validation_failed` responses. Invalid, noncanonical,
stale, or differently scoped cursors produce 422 `invalid_privacy_cursor`. All
outcomes use the existing global `Cache-Control: no-store`; successful responses
explicitly set it too.

The response is
`{schema_version: "1.0", items: [...], next_cursor: string|null}`. Each item
contains exactly `assessment_id`, `created_at`, `submitted_at`,
`retention_expires_at`, and `anonymized_at`. The latter three are nullable.
Timestamps are existing assessment metadata; no new policy deadline is inferred.
No email, name, invitation token, candidate answer, score, report, or total
count is returned. Canonical JSON examples are checked into
`apps/api/tests/fixtures/privacy_discovery/page.json` and `empty.json`.

Anonymized and unsubmitted assessments remain discoverable. Invitations without
an assessment produce an empty page; absent and other-tenant references produce
the same empty page. Returned IDs can be passed to the unchanged export/delete
routes; discovery does not change their existing lifecycle restrictions.

## Query and cursor behavior

The database selects only the five response columns through assessment →
invitation → profile → role, with the authenticated organization predicate in
both page and anchor queries. A page loads at most `limit + 1` rows; cursor
validation loads at most one uniquely identified anchor. Ordering is descending
`(created_at, assessment_id)`, including UUID tie-breaking. There is no offset,
unbounded result materialization, or count query. Existing indexes and joins are
used; query planner work can still grow with tenant data because this slice adds
no index/migration. Production-scale performance is not established.

The 103-character canonical base64url cursor contains a format version, selector
kind, tenant/filter/anchor UUIDs, and a normalized UTC creation timestamp. It is
not a credential. Validation checks scope and canonical re-encoding against the
current anchor before applying the keyset predicate. Deleted anchors invalidate
the cursor; clients restart from page one. Newly inserted earlier records are
not included midway through pagination; the listing is not a snapshot.

The endpoint records `privacy.assessments_discovered` against the actor user
using existing audit middleware. Audit metadata includes only HTTP method,
status, and outcome. The implementation adds no selector/cursor/body logging,
new collection, dependency, migration, or changes to `privacy.service`.
Infrastructure access logs remain subject to the existing redaction
requirements.

## Verification

Tests use isolated in-memory SQLite and synthetic fixtures, without services or
ports. They cover exact response fixtures, tenant isolation, permissions,
anonymized/unsubmitted rows, empty results, cursor scope/tampering/deleted
anchors, canonical encoding, timestamp ties, default/max limits, audit payload
allowlists, no-store errors/success, and projection/query result bounds.

Validation on November 4, 2026: **22 passed**, with **100% statement and branch
coverage** across discovery/router/schemas. Ruff lint/format and strict mypy on
the three changed application files plus discovery tests passed. Commands from
the repository root:

```sh
.venv/bin/python -m pytest apps/api/tests/test_privacy_discovery.py apps/api/tests/test_privacy.py -o addopts="--strict-config --strict-markers" --cov=app.privacy.discovery --cov=app.privacy.router --cov=app.privacy.schemas --cov-branch --cov-report=term-missing --cov-fail-under=100 -q
MYPYPATH=packages/shared/python .venv/bin/mypy --config-file apps/api/pyproject.toml apps/api/app/privacy/discovery.py apps/api/app/privacy/router.py apps/api/app/privacy/schemas.py apps/api/tests/test_privacy_discovery.py
.venv/bin/ruff check apps/api/app/privacy apps/api/tests/test_privacy_discovery.py
.venv/bin/ruff format --check apps/api/app/privacy apps/api/tests/test_privacy_discovery.py
```

The initial focused pytest invocation retained the repository-wide coverage
source from default addopts, so its 22 passing tests failed that unrelated
global coverage gate; the explicit scoped command above corrected the
invocation. The initial mypy invocation omitted the shared package search path;
the corrected command above passed. No dependencies were installed or altered.

PostgreSQL query plans, real browser integration, verified support contacts,
related-event traversal, and full rights-request workflows remain integration or
broader package work.
