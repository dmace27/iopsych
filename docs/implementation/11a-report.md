# 11A packaging preparation — 2026-11-04

Bounded preparation is complete; **full 11A is not complete**. Implementation
commit: `1158d94` (`Prepare provider-neutral API and web container packaging`),
based on committed integration `3602cb050e82969105828544af3fc08a78c16e32` in
child worktree `iopsych-11a-packaging`. This report is a separate documentation
commit so it can cite the exact tested implementation revision.

## Changes and assumptions

Owned files only: `.dockerignore`, `apps/api/Dockerfile`, `apps/web/Dockerfile`,
`deploy/compose.yaml`, `deploy/smoke.py`, `deploy/README.md`, and this report.
No shared contracts, migrations, dependency manifests, root Compose,
setup/startup scripts, root README, assessment content or interpretation
changed.

API packages the shared Python source at its editable-install location plus all
checked-in definitions/schemas at the monorepo-relative paths. Both images use
non-root production processes, direct exec-form commands, SIGTERM and no reload.
Compose gives a 35-second drain window and init forwarding. Migration execution
is explicit, separate from application startup, with no seed command. The
runtime image also supports the existing retention module as a separately
configured job; no scheduler has been provisioned.

Rehearsal is synthetic-only on project `iopsych_11a`, loopback ports
3106/8106/5546, and its own volume. Its public synthetic DB-owner credential is
a local shortcut, not a proposed hosted runtime identity. Auth/provider
credentials were absent; no emails, provider calls, candidate records, seed,
existing database reset, public deployment or push occurred. Other project
containers were untouched.

Coordinator authorized sequential builds in `msg_fb6a221bfa9d`; API and web
builds were serialized. Next's existing build used 14 workers internally; no
resource failure/OOM occurred. No dependency installation was run in the host
worktree, so the concurrently saved setup process was not raced.

## Commands and observed results

All commands ran from this child worktree. Build output was captured locally at
`/tmp/iopsych-11a-api-build.log` and `/tmp/iopsych-11a-web-build.log`; the
durable results are recorded here rather than depending on those temporary
files.

| Actual command                                                                                                                                                                                                                           | Result                                                                                                                              |
| ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| `docker version --format '{{.Server.Version}}'`                                                                                                                                                                                          | Docker server `29.8.0`.                                                                                                             |
| `docker compose -f deploy/compose.yaml config --quiet`                                                                                                                                                                                   | Passed.                                                                                                                             |
| `docker compose -f deploy/compose.yaml build api`                                                                                                                                                                                        | Passed; Python 3.12 runtime and shared-library installation succeeded.                                                              |
| `docker compose -f deploy/compose.yaml build web`                                                                                                                                                                                        | Passed; fresh container `npm ci`, shared TypeScript build, Next production webpack build/type checking, and `npm prune --omit=dev`. |
| `docker compose -f deploy/compose.yaml up -d --wait db`                                                                                                                                                                                  | Dedicated PostgreSQL 16 healthy; new `iopsych_11a_db-data` volume.                                                                  |
| `docker compose -f deploy/compose.yaml run --rm migrate`                                                                                                                                                                                 | All seven existing migrations applied to the new empty DB through `20260929_0007`.                                                  |
| `docker compose -f deploy/compose.yaml up -d --wait api`                                                                                                                                                                                 | API healthy on loopback 8106.                                                                                                       |
| `docker compose -f deploy/compose.yaml run --rm migrate alembic current`                                                                                                                                                                 | `20260929_0007 (head)`.                                                                                                             |
| `docker compose -f deploy/compose.yaml up -d --wait web`                                                                                                                                                                                 | Web healthy on loopback 3106.                                                                                                       |
| `python3 deploy/smoke.py`                                                                                                                                                                                                                | Passed: API `/health` 200, web HTML 200, unauthenticated internal proxy denied.                                                     |
| `docker compose -f deploy/compose.yaml exec -T web node -e 'if(process.getuid()===0) process.exit(1); console.log("PASS: web non-root uid",process.getuid())'`                                                                           | UID 1000.                                                                                                                           |
| `docker compose -f deploy/compose.yaml exec -T web node -e 'fetch(process.env.API_BASE_URL+"/health").then(async r=>{if(!r.ok)process.exit(1);console.log("PASS: private web-to-API HTTP",await r.text())}).catch(()=>process.exit(1))'` | Internal Docker DNS/API connection returned health JSON successfully.                                                               |
| `docker compose -f deploy/compose.yaml stop web api`                                                                                                                                                                                     | Both stopped promptly within the 35-second window.                                                                                  |
| `docker inspect iopsych_11a-api-1 iopsych_11a-web-1 --format '{{.Name}} exit={{.State.ExitCode}} oom={{.State.OOMKilled}}'`                                                                                                              | Both exit 143 (SIGTERM), `oom=false`; neither needed SIGKILL.                                                                       |
| `docker compose -f deploy/compose.yaml logs --no-color api --tail 8`                                                                                                                                                                     | Explicit application shutdown complete and server process finished.                                                                 |
| `docker compose -f deploy/compose.yaml up -d --wait api web` then `python3 deploy/smoke.py`                                                                                                                                              | Same-image restart and smoke passed.                                                                                                |
| `docker compose -f deploy/compose.yaml exec -T db psql -U iopsych_11a -d iopsych_11a -Atc 'SELECT version_num FROM alembic_version; SELECT count(*) FROM organizations;'`                                                                | After restart: head `20260929_0007`, zero organizations.                                                                            |
| `docker compose -f deploy/compose.yaml down`                                                                                                                                                                                             | Removed only rehearsal containers/network; retained its DB volume, no `--volumes`.                                                  |
| `node node_modules/prettier/bin/prettier.cjs --write deploy/README.md deploy/compose.yaml`                                                                                                                                               | Formatted owned documentation/Compose.                                                                                              |
| `git diff --cached --check`                                                                                                                                                                                                              | Passed before implementation commit.                                                                                                |

The API asset/identity/schema probe also passed using this exact stdin program:

```sh
docker compose -f deploy/compose.yaml exec -T api python - <<'PY'
import json, os
from pathlib import Path
import iopsych_contracts
from app.invitations.service import PILOT_DEFINITION_PATH
from app.database.config import DatabaseSettings
from sqlalchemy import create_engine, text
assert os.getuid() == 10001
assert json.loads(PILOT_DEFINITION_PATH.read_text())
assert len(list(Path('/opt/iopsych/packages/shared/definitions/v1').glob('*.json'))) == 3
with create_engine(DatabaseSettings().database_url).connect() as conn:
    assert conn.scalar(text('SELECT version_num FROM alembic_version')) == '20260929_0007'
    assert conn.scalar(text('SELECT count(*) FROM organizations')) == 0
print('PASS: non-root API, shared import, definition assets, schema head, no seeded organizations')
PY
```

Tested local image IDs (tags `iopsych-api:11a-local`, `iopsych-web:11a-local`):

- API:
  `sha256:c98e4619a4e66e6919a439d4acba7395cf6e50faf82b5fd095833395bff59da6`.
- Web:
  `sha256:fb84519f7e4d60b5fb03159b815ba1314f87ac13297f8437d62f379f5ef5640f`.

These were built from the working files later committed as `1158d94`; the local
image label is `11a-local`, not a claimed release revision. Deployment
instructions set `REVISION` explicitly and require promotion by digest. Base
image tags and Python transitive dependencies remain floating, so byte-identical
rebuilds are not claimed.

## Findings, skips, blockers and remaining gates

- No bounded-preparation blocker remains. All targeted packaging checks passed.
  No full unit suite or redundant host build was run, as requested.
- npm's install reported 15 vulnerabilities (11 moderate, 3 high, 1 critical);
  the production prune reported 2 (1 high, 1 critical). These are npm summaries,
  not an independent exploitability assessment. Coordinator notified in
  `msg_eac9977f52d7`; dependencies were not changed. Current production
  dependency review/remediation and image/full-history scans remain release
  gates.
- Same-image restart is not a prior-release rollback, populated-data migration,
  backup restore or historical interpretation rehearsal. No active-request drain
  load test was run; observed shutdown is idle SIGTERM behavior.
- 6A is not integrated into this baseline; rerun packaging after integration,
  especially synthetic-login disabled behavior and setup compatibility.
- Hosting/vendor/region, managed DB, private ingress, TLS, secret injection,
  separate runtime/migration DB grants, image registry/CI deployment, readiness,
  rollback/forward-fix and restore/deletion replay still need actual
  configuration and staging evidence. `deploy/README.md` lists concrete
  configuration and release steps without claiming provisioning or approval.
- The existing `/health` is liveness only. Local healthy status does not prove
  schema readiness, configured identity/delivery, Secure-cookie browser
  behavior, real-provider integration, full role/candidate/privacy journeys or
  release eligibility. Those checks were intentionally skipped here and remain
  owned by 6B, 7–10, 11B/11C and 12A–12C as appropriate.
- No I-O, privacy, product or real-participant approval is implied. Full 11A and
  final release remain open until hosting decisions and staging/recovery gates
  pass. Next eligible work is coordinator review/integration, revalidation after
  6A, then decision-backed staged deployment preparation.
