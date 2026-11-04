# 11A integrated local packaging verification

Verified 2026-11-04 against **`4c7caf31254c4027b917f1afb89cfe08dd428e0e`**. The
bounded packaging verification passed. This is not deployment, rollback, release
approval, or full 11A acceptance. Application/deployment files and
migration/dependency ownership were respected; only this report changed.

## Isolation and build provenance

Read the final implementation plan including the accelerated schedule, progress
ledger, 11A packaging report, 6C report/contract, Dockerfiles, Compose and
migration upgrade tests. No applicable ancestor/root/docs AGENTS file was
present. No Fast setting was toggled; this task does not claim an independently
observed live tier.

Docker server: `29.8.0`. Both production images were rebuilt sequentially from a
clean `git archive HEAD` export, with normal Docker layer caching. Builds used
the tracked Dockerfiles and lockfile, not host node_modules or ignored
configuration. The build context was `/tmp/iopsych-packcheck-5mxqgbl3/source`;
the untracked, resolved Compose configuration was
`/tmp/iopsych-packcheck-5mxqgbl3/compose.json`.
`docker compose --profile tools config --format json` supplied the base config;
the local copy replaced project, network, volume, image names, DB configuration
and host ports. No tracked Compose override was added.

- Project/network: `iopsych_packcheck` / `iopsych_packcheck_default`.
- New volume: `iopsych_packcheck_db-data`; database/user: `iopsych_packcheck`.
- Loopback ports: web `3132`, API `8132`, PostgreSQL `5572`.
- Only a public synthetic local DB password was injected at runtime. No signing,
  email or provider credentials were supplied, and no invitation was sent.
- Existing containers/volumes, including the earlier 11A volume, were untouched.
  Ports 3000/8000/8001 were not bound on the host.

Both image tags contain the full tested revision and both OCI revision labels
exactly equal that revision:

| Image                                                            | Docker image ID                                                           |
| ---------------------------------------------------------------- | ------------------------------------------------------------------------- |
| `iopsych-packcheck-api:4c7caf31254c4027b917f1afb89cfe08dd428e0e` | `sha256:0941cdf14e55de17f6ede2cb76c2b6ef16bfb018af4a0b490398d74a8cd90f19` |
| `iopsych-packcheck-web:4c7caf31254c4027b917f1afb89cfe08dd428e0e` | `sha256:0a9eae55b3caa9589b79472eb70ed269567836d3da55daae2324856bd6f628ed` |

## Exact targeted execution and results

In these commands, `C=/tmp/iopsych-packcheck-5mxqgbl3/compose.json`. Temporary
logs and the standalone upgrade probe are in the same parent directory; the
results below are durable evidence independent of those temporary files.

| Command or probe                                                                                                   | Observed result                                                                                                                                                                                                                                                                                  |
| ------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `docker compose -f "$C" config --quiet`                                                                            | Exit 0 after isolated config generation.                                                                                                                                                                                                                                                         |
| `docker compose -f "$C" build api`                                                                                 | Exit 0; packaged Python 3.12.16 runtime, shared editable library and migration assets.                                                                                                                                                                                                           |
| `docker compose -f "$C" build web`                                                                                 | Exit 0; fresh container npm ci, shared build, Next **16.4.1** webpack production compilation, TypeScript, static pages and production prune passed. Both npm audit summaries reported zero vulnerabilities; no engine warning.                                                                   |
| `docker compose -f "$C" up -d --wait db`                                                                           | Newly created volume/database healthy.                                                                                                                                                                                                                                                           |
| `docker compose -f "$C" run --rm migrate`                                                                          | Exit 0; all eight migrations applied to empty public schema, head `20261104_0008`.                                                                                                                                                                                                               |
| `docker compose -f "$C" up -d --wait api` and then `up -d --wait web`                                              | Both healthy.                                                                                                                                                                                                                                                                                    |
| `docker compose -f "$C" exec -T api python - < /tmp/iopsych-packcheck-5mxqgbl3/upgrade-probe.py`                   | Exit 0; populated packaged 0007-to-0008 upgrade passed; details below.                                                                                                                                                                                                                           |
| API Python asset/identity probe via `exec -T api python -`                                                         | UID **10001**; shared import succeeds; three v1 definition JSON files and schema JSON assets present; runtime and Alembic frozen definitions both match canonical SHA-256 `021233ca4dab9c86b87aeabca88f503bf7c70fd0b0d324c64e788b620aeb6e3c`; public schema at 0008 with **zero organizations**. |
| Web Node probe via `exec -T web node -`                                                                            | UID **1000**, Node **22.23.4**, installed Next **16.4.1**. Packaged semver confirms Node satisfies root `^22.22.2 \|\| ^24.15.0 \|\| >=26.0.0` and Next `>=20.9.0`.                                                                                                                              |
| HTTP urllib probes to `http://127.0.0.1:8132/health`, `http://127.0.0.1:3132/`, `/api/internal/auth/me`            | Respectively **200** with API health JSON, **200** with HTML, **401** unauthenticated proxy denial.                                                                                                                                                                                              |
| Web `fetch(process.env.API_BASE_URL+'/health')`                                                                    | Internal Docker DNS/API HTTP **200** with health JSON.                                                                                                                                                                                                                                           |
| `docker compose -f "$C" stop db`, then `curl --fail --silent http://127.0.0.1:8132/health`, then `up -d --wait db` | Health remained **200** while own DB was stopped; DB restarted healthy. Liveness is independent of database availability.                                                                                                                                                                        |
| HTTP probe to `http://127.0.0.1:8132/ready`                                                                        | **404**: this revision has no readiness endpoint; not counted as DB readiness evidence.                                                                                                                                                                                                          |
| `docker compose -f "$C" stop web api` timed with Python monotonic clock                                            | **0.391 seconds**, within 35-second grace; both exits **143**, OOM false, no SIGKILL. API logs explicitly show application shutdown complete and server process finished.                                                                                                                        |
| `docker compose -f "$C" up -d --wait api web` and repeat health/web SQL probes                                     | Healthy same-image restart; public 0008 and zero organizations persist; populated upgrade schema remains at 0008 with seven invites. Web HTTP **200**.                                                                                                                                           |
| `docker compose -f "$C" down`                                                                                      | Only own containers/network removed; own synthetic volume retained, no volume deletion.                                                                                                                                                                                                          |

The Node build/runtime base resolved to
`node:22-bookworm-slim@sha256:4b150b48b4116e2a22f2c39cc27025fbf4f153e2078fd3b14d159fdb5c7279da`.
Floating base tags and Python transitive dependencies still preclude a claim of
byte-identical future rebuilds.

## Populated migration evidence

The standalone probe adapts the body of
`apps/api/tests/test_assignment_upgrade.py::test_populated_upgrade_preserves_assignments_and_original_interpretation`
and its `responses()` helper from `test_reports.py`, without adding pytest or
any other dependency to the runtime. It executes inside the production API
image, using its installed application, Alembic configuration, migrations and
frozen assets. It creates a uniquely named schema only inside
`iopsych_packcheck`, sets that connection's search_path, upgrades to 0007, then
inserts synthetic fixtures. It does not run the original test's downgrade
portion or touch an existing DB.

The passing probe checks seven states: unopened, consented, expired, submitted,
unknown version, malformed and anonymized. Recognized legacy assignments receive
the exact frozen v1 snapshot and replay unchanged draft scores; unsupported and
anonymized history remain NULL. Existing definition/response/score JSON and the
saved report remain identical, and the v1 reader returns the original report.
Ordinary status updates succeed. PostgreSQL rejects assignment replacement,
assignment clearing and NULL-history reassignment with the immutable-assignment
error. After restart the successful schema still holds seven invitations
at 0008. The public schema remains unseeded; seed data exists only in the
synthetic probe schema. This is upgrade coverage, not a rollback/restore
rehearsal.

## Secret exclusion, failures and remaining owners

The clean export excludes ignored host files by construction. Runtime
`/opt/iopsych` checks found no `.env*` or `.git`; the recursive web check
additionally found no `.npmrc`, `id_rsa` or `id_ed25519`. Image configuration
contains no app credential values; API base-image public GPG fingerprint is not
a signing secret. A bounded clean-export content scan for private-key headers,
AWS access-key IDs, GitHub token patterns and OpenAI project-key patterns
returned zero matches. This does not replace full-history/image-layer secret
scanning or an OS vulnerability assessment; those remain the security owner's
release gates.

Two local config-generation attempts failed before any container mutation: the
first omitted the tools profile and could not find `migrate`, and the second
looked under `/tmp` while macOS tempfile had selected its per-user directory.
The corrected configuration explicitly uses `/tmp` and includes tools. The first
populated probe stopped at 0007 because its extracted helper lacked an
`AssessmentDefinition` import. Adding that import and the definition-path import
to the temporary probe, then using a fresh unique schema, produced the passing
result above. The incomplete schema remains only in the retained isolated
volume. These were verification-harness issues; no application fix is required
for them.

No packaging regression requiring an application change was found. Readiness is
absent at this tested revision: **11B readiness owner/coordinator** must
integrate and verify that separately; this report does not imply later changes
were tested. **Packaging/dependency owners** retain immutable base/dependency
pinning review. **Security owner** retains comprehensive secret/layer/OS
scanning. **Coordinator** owns integration, hosted TLS/private ingress and
privilege separation, controlled rollback/forward-fix, provider verification,
backup/restore and release decisions.

No full suite, duplicate browser suite, real email, public deployment, push,
purchase, external provider or existing database reset occurred. The accelerated
time target did not waive any acceptance gate. Full hosted 11A and release
acceptance remain pending.
