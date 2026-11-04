# 6C retained-definition integrity repair

Base revision: `360c5dc` (includes integrated 6C backend `6a8fd01`). Scope:
registry, assignment tests, and this report; no contracts, migrations, frozen
definitions, dependency manifests, or scientific semantics changed.

## Change

Assignment reads now require both the retained v1 SHA-256 and a matching
computed canonical payload hash. Matching identifiers and scoring configuration
alone cannot authorize replacement item wording, construct assignments, titles,
or status, even with an attacker-recomputed hash.

A separate `RETIRED_DEFINITIONS` policy uses definition ID, version, and
checksum and blocks new issuance, including synthetic or reviewed issuance.
Retirement never edits the frozen artifact or stored snapshot. Historical
definition reads, scoring, matching, and persisted report reads continue using
the retained data. The former retirement test incorrectly treated a changed
historical status as a valid retained payload; it now changes issuance policy
and preserves the snapshot.

## Dispatch inspection

- `legacy_definition` checks the retained artifact checksum before parsing.
- `new_assignment` applies retirement before reviewed/synthetic eligibility;
  reviewed eligibility remains empty in production configuration.
- `read_assignment` validates schema, exact retained content, scorer
  configuration, scorer availability, and matcher availability.
  `definition_response` uses it.
- Submission reads the assignment before `score_assignment`; the latter
  dispatches the validated assignment to the retained scorer. Both skipped and
  answered response fixtures preserve the direct v1 scoring result.
- Report generation reads the assignment, validates stored score shape, and
  checks definition ID/version and scoring version before matcher dispatch.
  Tests now independently reject mismatch in each of those three fields.
- Report reads validate payload shape and equality of stored/payload algorithm
  versions against retained report readers, without invoking matching again.
  Report creation and subsequent historical reads remain available after
  retirement.
- Typed scorer/matcher helpers are internal consumers of `read_assignment`
  output; they are not standalone untrusted-payload entry points. Future callers
  must preserve that boundary.

## Evidence

Commands ran in this isolated child worktree using synthetic fixtures and
in-memory SQLite. No servers, PostgreSQL databases, or reserved ports were used.

From `apps/api`:

```sh
../../.venv/bin/pytest tests/test_assignments.py -o addopts='--strict-config --strict-markers --cov=app.assignments.registry --cov-branch --cov-report=term-missing --cov-fail-under=100'
MYPYPATH=../../packages/shared/python ../../.venv/bin/mypy app/assignments/registry.py tests/test_assignments.py
```

Results: **37 passed, zero skips**; registry **100% statement and branch
coverage** (81 statements, 10 branches, zero missing or partial branches); mypy
passed for both scoped files. Coverage scope is deliberately the registry, not
the entire application; its threshold remains 100% with branch measurement
enabled.

From the repository root:

```sh
.venv/bin/ruff check apps/api/app/assignments/registry.py apps/api/tests/test_assignments.py
.venv/bin/ruff format --check apps/api/app/assignments/registry.py apps/api/tests/test_assignments.py
git diff --check
```

All passed. An initial mypy invocation without `MYPYPATH` could not resolve the
local shared package; the explicit repository package path corrected the
invocation. An initial formatting check identified one tuple layout, which was
formatted.

Regression sensitivity was checked by temporarily running the new
recomputed-hash tests against the unmodified base registry, then restoring the
fix in a `finally` block. The baseline incorrectly accepted item wording,
balanced construct swaps, title, and status changes: **4 failed / 2 passed**, as
expected. The fixed suite rejects all six mutations with
`unsupported_assessment_version`; each mutated fixture first passes the
assessment schema, so rejection tests retained-content recognition rather than
malformed input alone.

## Remaining boundaries

This is the requested integrity repair, not full 6C or release acceptance. No
new PostgreSQL migration/rehearsal or browser evidence is claimed. Existing
broader integration checks and actual content/product approvals remain
coordinator work; future versions must add retained entries rather than replace
v1 content. Next action: independently review and integrate this scoped commit,
then include it in the combined integration checks.
