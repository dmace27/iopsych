# Current frozen packaging verification

Verified 2026-11-04 at **58eaad8d75302425af522e6f09b0c5e60ff13cce**.
**Overall packaging gate failed: the production web image does not build.**
The API image, controlled migrations through 0009, readiness/liveness and API
restart checks passed. This is local synthetic evidence, not hosted deployment,
rollback, restore, full 11A acceptance, or release approval. Incoming migration
0010 and any later integration are **not covered**.

## Scope and isolation

Read the final implementation plan, previous `11a-integrated-check.md`, packaged
Dockerfiles/Compose, migration 0009 and runtime health/telemetry configuration.
No applicable ancestor/root/API/docs AGENTS.md was found. No app, dependency,
migration or deployment configuration was edited; this report is the only
tracked change. No model/tier setting was changed or independently verified.

Both builds used an actual clean `git archive` of the frozen revision, ordinary
Docker layer caching, and the tracked Dockerfiles. Docker server was 29.8.0.
Temporary export, config, probes and logs: `/tmp/iopsych-current-j8vezo3z`.
The resolved config came from `docker compose --profile tools config --format
json`, with local-only project/image/volume/port/database replacements.

- Unique project/network: `iopsych_current_j8vezo3z` / corresponding `_default`.
- New retained volume: `iopsych_current_j8vezo3z_db-data`; database/user `synthetic`.
- Assigned loopback ports: API 8177, PostgreSQL 5597, web 3157 (never started).
- Only a public synthetic DB password was supplied; no signing/provider/mail
  credentials, real mail, purchases, pushes, existing DB resets or hosted actions.
- Ports 3000/8001/8000/5432 on the host and other containers/volumes were untouched.
- Own containers/network were removed with `down` without `--volumes` after checks.

## Actual builds and blocking finding

With `C=/tmp/iopsych-current-j8vezo3z/compose.json`:

| Command | Result |
| --- | --- |
| `docker compose -f "$C" config --quiet` | Passed. |
| `docker compose -f "$C" build api` | Passed; packaged image below. |
| `docker compose -f "$C" build web` | **Failed**, exit 1 in Dockerfile line 12: production TypeScript check cannot resolve eight fixture imports. |

API tag: `iopsych-current-api:58eaad8d75302425af522e6f09b0c5e60ff13cce`.
Image ID: `sha256:68d335a523fd60ab2235f7c12d660cfc9c97a19a610712bb1c24667138da3d33`.
OCI revision label equals the frozen revision. The Python base resolved to
`python:3.12-slim-bookworm@sha256:e697c81897302a4c4333bade000d98038fbb21eb064f8ee1fd42d02ebcd9d337`.

Web `npm ci` succeeded (audit reported zero vulnerabilities), shared compilation
and Next 16.4.1 webpack compilation succeeded, then TypeScript reported TS2307
for all imports in `apps/web/lib/report-trace-fixtures.ts:1–8`. Those imports
reference `../../api/tests/fixtures/report_trace/{complete,skipped,two-skipped,all-skipped}.{trace,source}.json`.
The web Dockerfile copies `apps/web` and shared packages but not those API test
fixtures; `apps/web/tsconfig.json` includes all TypeScript files and excludes
only node_modules. This is a clean-image packaging regression, not an npm
installation failure. No replacement image was fabricated and no temporary
application patch was used. **Coordinator/packaging owner must repair the build
context or fixture/typecheck boundary and rerun the image build.**

Web base resolved to
`node:22-bookworm-slim@sha256:4b150b48b4116e2a22f2c39cc27025fbf4f153e2078fd3b14d159fdb5c7279da`.
No web runtime identity/assets, HTTP/proxy, shutdown or persistence claim is made.

## Bounded API and database evidence

| Command/probe | Observed result |
| --- | --- |
| `up -d --wait api` | New isolated database and production API healthy. |
| `run --rm migrate` | Empty public schema upgraded through all nine migrations to `20261104_0009`; no automatic organizations or delivery rows. |
| `exec -T api python - < upgrade-probe.py` | Passed populated 0008→0009 preservation and historical assignment/report checks described below. |
| `exec -T api python - < runtime-probe.py` | UID 10001; shared Python import and definition/schema JSON assets present; packaged head 0009; cryptography 50.0.2 imports and ephemeral in-memory Fernet encrypt/decrypt round-trip succeeds. |
| In-container HTTP probes | `/health` and `/ready` 200; responses have UUID `X-Request-ID`; 1,048,577-byte body rejected with 413 against the 1,048,576-byte default. |
| Synthetic unknown path/query probe and log check | 404; raw synthetic path and query marker absent from API logs, with allowlisted completion telemetry present. |
| Host `http-probe.py 200` on port 8177 | `/health` 200 and `/ready` 200. |
| Change only own public Alembic version marker to 0008; `http-probe.py 503`; restore marker to 0009 | Liveness remained 200, readiness became 503 and recovered to 200. This was mismatch fault injection, not a downgrade or rollback. |
| `stop db`; `http-probe.py 503`; `up -d --wait db`; `http-probe.py 200` | Liveness remained 200 during DB outage; readiness 503 then recovered to 200. |
| Timed `stop api` and container inspect | 0.412 seconds; exit 143, OOM false; explicit application shutdown complete/server finished logs, no SIGKILL. |
| `up -d --wait api`; repeat runtime and HTTP probes | Passed: public head 0009, zero organizations/delivery rows; populated schema head 0009 and seven invitations persisted; health/readiness 200. |
| `down` | Own containers/network removed; own synthetic volume retained. |

The standalone populated probe adapts the previous report's extracted assignment
upgrade probe, using only the installed production dependencies and migration
assets. It creates schema
`current_upgrade_c8e66d060558491e9d38b2fd51c5e15f` in the new synthetic database,
sets connection search_path, populates seven legacy invite states at 0007, then
migrates to 0008. Before applying 0009 it snapshots every row of every existing
table (except the Alembic version marker) as ordered PostgreSQL JSONB. After
0009 every snapshot is identical, the new delivery table is empty, historical
assessment/response/score/report JSON remains readable, and immutable assignment
replacement/clearing/NULL-history reassignment still raises database errors.
No downgrade, rollback, full test suite or duplicate browser suite was run.

## External calls, harness limitations and remaining gates

Initial runtime checks used a Docker `internal: true` network; `/proc/net/route`
showed no default gateway. No provider credentials or adapters were configured,
and readiness reads only packaged migration heads and the local DB marker.
Next telemetry is disabled in the tracked Dockerfile. Builds necessarily used
package registries/base-image downloads. Docker suppressed host port forwarding
on the internal network, so the initial host HTTP probe failed with connection
refused; this is not a readiness failure. Own containers/network were recreated
with normal networking and the same retained volume for successful assigned-port
checks. No external provider requests were intentionally made or observed in
logs; there was no packet capture, so this is **not proof of zero attempted
external traffic during the normal-network portion**.

The attempted initial missing-schema HTTP check did not execute successfully
because of that forwarding issue; missing-schema readiness is not counted.
The first export attempt also stopped before container mutation because host
Python 3.9 lacks the newer tar extraction `filter` argument; extracting the
trusted local Git archive without that argument resolved the harness issue.

Runtime API assets contained no `.env*` or `.git`; a bounded clean-export scan
for private-key headers, AWS IDs, GitHub tokens and OpenAI project keys returned
zero matches. This is not full-history/image-layer secret or OS vulnerability
scanning. Floating base tags and unlocked transitive Python dependencies prevent
a byte-identical future rebuild claim. Completion logs reported release ID
`unknown`: Compose does not supply `IOPSYCH_RELEASE_ID`, despite the correct OCI
image label; coordinator should wire runtime release attribution if required.

Coordinator remains sole integrator/migration owner. Remaining work includes
the web packaging fix/rebuild and runtime checks, migration 0010 verification,
comprehensive security scanning, hosted TLS/private ingress and privilege
separation, configured-provider validation, backup/restore, rollback/forward-fix
and release approvals. No hosted deployment or rollback claim is made.
