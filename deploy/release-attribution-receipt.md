# Release attribution receipt

Validated on 2026-11-04 from isolated checkout baseline `91c2774`, which
includes canonical fixture COPY fix `1a5b3c0`. Only deployment configuration,
its focused tests and documentation changed; Dockerfiles, application code and
dependencies were untouched.

Compose now uses supplied `REVISION` consistently for API/web image tags, build
arguments and API/migration/web runtime `IOPSYCH_RELEASE_ID`. Missing or empty
values resolve to `unknown`. The existing API telemetry allowlist is unchanged.

Checks completed:

- Synthetic
  `env -i PATH="$PATH" REVISION=synthetic-validation docker compose --env-file /dev/null -f deploy/compose.yaml config --quiet`:
  passed.
- `python3 -m unittest discover -s deploy -p 'test_*.py' -v`: six model tests
  passed, covering supplied SHA/identifier, absent/empty revision and
  conflicting host runtime IDs across API, migration and web.
- From `apps/api`, synthetic in-memory database environment and
  `../../.venv/bin/python -m pytest tests/test_telemetry.py -k release --no-cov -q`:
  nine passed, 23 deselected. Initial subset execution passed all nine cases but
  failed the global 100% coverage gate; the focused rerun disabled coverage.
- Prettier checked the Compose/README formatting; `git diff --check` passed.

No image builds, container starts, database operations, hosted deployments or
external messages were performed. Final integrated image verification remains
with the coordinator: include `1a5b3c0`, build from the final source revision,
and compare OCI image labels and actual API completion telemetry to that
revision. These model checks do not establish hosted release readiness.
