# Web packaging repair and clean-image verification

Verified 2026-11-04, from clean exported revision
`2ea2fb45d3b8e2d46ee08b307215177c9d3188d8` (parent
`b70496563b5ec00e68c71264f99bc537dd1f7202`). The bounded packaging gate passes.
This supersedes the web build blocker in report commit `16802af`; it is not
hosted deployment or full release acceptance.

## Change and execution policy

`apps/web/Dockerfile` now copies only `apps/api/tests/fixtures/report_trace`
into the build stage. The web fixture helper imports eight canonical JSON files,
and the normal production TypeScript check includes that helper. No typecheck
exclusions, ignored build errors, dependency changes, fixture duplication, or
application changes were introduced. The runtime stage does not copy the API
directory; this was checked in the actual image.

Work stayed in `AbhiNutakki/iopsych-package-repair`. Read the accelerated
schedule, progress ledger, `apps/web/AGENTS.md`, installed Next.js TypeScript
configuration guide, and prior packaging report. No applicable ancestor
AGENTS.md was found. No installer was running when checked; Docker installs used
the independent clean export. Live `orca terminal show` preview displayed
`GPT-6-Astra medium fast`; no mode toggle was performed.

## Reproduction and isolation

Both images were built with the tracked Dockerfiles from `git archive` of the
exact revision above, without ignored files or host dependencies. Ordinary
Docker layer caching was enabled; this is a clean build input, not a no-cache
build or byte-identical reproducibility claim.

Temporary evidence directory:
`/var/folders/nc/zsxwwgbd0fj4q3mqvr9dxns00000gn/T/iopsych-repair-saq3dywx`. It
contains `source.tar`, extracted `source/`, resolved `compose.json`,
`build-web.log`, `build-api.log`, `runtime.log`, `runtime-resume.log`,
`web.log`, and `cleanup.log`. The standalone assertion harness is
`/tmp/iopsych-repair-probe.py`; the directory pointer is
`/tmp/iopsych-repair-active`. These temporary files are local evidence, not
committed dependencies.

Compose JSON came from the exported `deploy/compose.yaml` using
`docker compose --profile tools config --format json`, with unique image tags,
project/network/volume names, synthetic database credentials and assigned host
ports. Project: `iopsych_repair_saq3dywx`; fresh volume:
`iopsych_repair_saq3dywx_db-data`; database/user: `synthetic`. Only loopback
ports web3157/API8177/PostgreSQL5597 were used.

With `C` set to the evidence directory's `compose.json`, executed:

```sh
docker compose -f "$C" config --quiet
docker compose -f "$C" build web
docker compose -f "$C" build api
python3 /tmp/iopsych-repair-probe.py
python3 /tmp/iopsych-repair-probe.py --resume
docker compose -f "$C" exec -T db psql -U synthetic -d synthetic -Atc 'select version_num from alembic_version;'
docker compose -f "$C" down
```

Image tags use `iopsych-repair-web:<revision>` and
`iopsych-repair-api:<revision>`. Inspected image IDs:

- Web:
  `sha256:637c15f6cdac37f81781663d7ca63e7610ed3d202003c83b7c13ac2b5f075b15`.
- API:
  `sha256:767f39b722cfcff2353afe68c23b381ab2c297b42d4f815175bb8a6e162454fa`.

Web OCI revision label matches the exported revision. Both builds completed with
exit0; web ran shared compilation, Next16.4.1 webpack compilation, full
production TypeScript checking (4.7 seconds), static generation, and
`npm prune --omit=dev`. The npm build output reported zero vulnerabilities; no
fresh comprehensive security audit is claimed.

## Observed runtime results

| Check                         | Actual result                                                                                                                    |
| ----------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| Fresh uninitialized DB        | API `/health`200; `/ready`503.                                                                                                   |
| Controlled `run --rm migrate` | All migrations through `20261104_0010` passed; API readiness became200.                                                          |
| Actual production web startup | Compose healthcheck passed; `/`, `/sign-in`, `/api/health` returned200. `/` follows the application's redirect.                  |
| Rendered static assets        | All11 discovered `/_next/` JavaScript/CSS assets returned200.                                                                    |
| Candidate proxy               | Web503 problem body exactly equaled direct API503, code `invitation_service_unavailable`, with no signing configuration.         |
| Runtime filesystem/identity   | Node UID1000/GID1000; `.next/BUILD_ID` present (`JloMuhR41WafL9ZvDt8L6`); `/opt/iopsych/apps/api` absent.                        |
| Own database stopped          | API health200/readiness503; web liveness200.                                                                                     |
| Own database restarted        | API readiness recovered200.                                                                                                      |
| Timed `stop web`              | 0.1696 seconds; exit143; OOM false; completed inside35-second grace period without SIGKILL. No in-flight request draining claim. |
| Web restarted                 | Compose web/API/DB healthy; web liveness200; API health/readiness200.                                                            |
| DB head after restart         | SQL returned `20261104_0010`.                                                                                                    |
| Cleanup                       | Own containers/network removed with `down`; fresh synthetic volume retained.                                                     |

The first probe expected404 for an unknown invitation, but the unconfigured
signing service correctly returned503. The harness assertion failed at that
point; the corrected resume probe compared direct and proxied503 bodies and
passed all remaining checks. No application workaround or secret was added, and
the already-completed fresh migration was not rerun/reset.

## Skips, limitations, and remaining work

No full unit/browser suite was rerun for this three-line build-input repair. No
populated migration0010 upgrade, authenticated candidate journey, configured
provider, real email, hosted readiness/TLS, rollback, restore, or load/draining
test was performed. Web `/api/health` and Compose web health are liveness
checks; dependency readiness evidence is from the API `/ready` endpoint.

No outstanding blocker remains for this bounded packaging repair. Integration
review and the broader release gates remain with the coordinator. There were no
pushes, purchases, deployments, production secrets, existing database resets,
main changes, or use of protected host ports3000/8001/8000/5432. Build registry
downloads used network access; no packet capture or zero-egress claim is made.
Only public synthetic DB credentials were configured. Existing containers and
volumes were left intact.
