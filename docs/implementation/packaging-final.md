# Final clean production-image verification

Verified 2026-11-04 against `5cde2e7cc9b98fe8bd25bc7e38c91afa7b20090e` in
isolated child `AbhiNutakki/iopsych-final-packaging`. This receipt covers image
builds only, not runtime, staging, full 11A or release acceptance.

Read applicable web AGENTS, final plan/progress, 11A reports, prior packaging
failure/repair receipts, current provider-neutral topology and deployment
runbook. Live terminal displayed `GPT-6-Astra medium` without Fast; no tier
toggle, purchase or additional service was used. Saved setup completed with
marker `__ORCA_SETUP_COMPLETE__:ccc86195-6a90-4b70-a734-72a5c5113622:0` before
builds.

Build input was a clean `git archive` of that revision, extracted at
`/tmp/iopsych-final-verify-sfwsfhic/source`; no host dependencies, ignored
configuration or credentials entered the context. Ordinary Docker layer caching
was enabled; this is not a no-cache or byte-identical reproducibility claim.
Docker server was 29.8.0 with approximately 8.3 GB allocated memory. API ran
first; coordinator then allocated the web slot after browser build cleanup. Only
one image build ran at a time in this lane.

## Commands and results

With `P=/tmp/iopsych-final-verify-sfwsfhic` and `R` equal to the full revision:

```sh
docker build --progress=plain --build-arg REVISION="$R" \
  -t iopsych-final-verify-api:5cde2e7-ctx038e \
  -f "$P/source/apps/api/Dockerfile" "$P/source"
docker build --progress=plain --build-arg REVISION="$R" \
  -t iopsych-final-verify-web:5cde2e7-ctx038e \
  -f "$P/source/apps/web/Dockerfile" "$P/source"
REVISION="$R" docker compose --env-file /dev/null \
  -f "$P/source/deploy/compose.yaml" config --quiet
python3 -m unittest discover -s deploy -p 'test_*.py' -v
```

API build exited 0: fresh dependency installation, shared editable package,
definitions/schemas, application and migration COPY steps completed. Installed
security pins include cryptography 50.0.2 and PyJWT 2.15.1. Compose
configuration validation exited 0; all six existing release-attribution model
tests passed. No full API or browser suite was duplicated.

Web build exited 0: fresh `npm ci`, shared TypeScript compilation, Next 16.4.1
webpack production compilation, full TypeScript checking, six static pages,
build tracing and `npm prune --omit=dev` all completed. No build gate was
skipped or weakened. Both npm summaries reported zero vulnerabilities; npm
warned that pinned eslint 9.39.5 is deprecated/unsupported. This warning is
reported without changing the coordinator-owned lockfile; it is not a fresh
comprehensive security audit. No other build error was observed.

`docker image inspect` verified both OCI revision labels exactly equal the
source revision and configured users API `10001:10001`, web `node`:

- `iopsych-final-verify-api:5cde2e7-ctx038e`:
  `sha256:f8df028375f69726307502073a206b1bc0dfb528f60b146885c0a7a41e9dd14d`.
- `iopsych-final-verify-web:5cde2e7-ctx038e`:
  `sha256:a594a50b3d2a795019cb970a386cc2e8e2f3d6c0b0180b2c7cdd54b803144536`.

Local complete logs: `$P/api-build.log` and `$P/web-build.log`.

## Boundaries and remaining gates

No packaging source or dependency changes were made. Full fixture COPY, security
pins, normal build/typecheck gates, non-root runtime configuration and revision
attribution remain intact. Only this receipt is committed.

No application containers/services were started; no database, migration, seed,
real mail, provider credentials, public deployment or push was used. Package
registry downloads occurred during image builds. No runtime asset/import,
health/readiness, shutdown, populated migration, rollback, restore, hosted TLS,
Auth0/Resend or current browser acceptance is claimed by this check. Image/base
security scans and fully locked Python transitive reproducibility were not run.
Coordinator integration and all outstanding
hosted/manual/content/privacy/release gates remain separate; later integration
revisions are outside this receipt.
