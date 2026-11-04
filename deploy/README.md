# Provider-neutral packaging preparation

This directory packages the existing Next.js / FastAPI / PostgreSQL topology. It
does not select a hosting vendor or provision staging. Full 11A remains gated by
6A integration, the hosting decision, and actual staging and rollback rehearsal.
No startup script is replaced. No command automatically seeds data or sends
mail.

## Isolated local rehearsal

Run from the repository root with Docker Compose v2. Build sequentially to limit
contention with other workers. These commands use only project `iopsych_11a`,
loopback ports web 3106, API 8106, DB 5546, and a dedicated persistent volume.
Do not change the project name to an existing project or run `down --volumes`.

```sh
export REVISION=$(git rev-parse HEAD)
docker compose -f deploy/compose.yaml config --quiet
docker compose -f deploy/compose.yaml build api
docker compose -f deploy/compose.yaml build web
docker compose -f deploy/compose.yaml up -d --wait db
# Explicit, single-run release operation; never part of service startup.
docker compose -f deploy/compose.yaml run --rm migrate
docker compose -f deploy/compose.yaml up -d --wait api web
python3 deploy/smoke.py
# Inspect schema separately: /health is liveness only.
docker compose -f deploy/compose.yaml run --rm migrate alembic current
# Graceful stop; retains the database and its history.
docker compose -f deploy/compose.yaml stop web api
docker compose -f deploy/compose.yaml down
```

Local database credentials are intentionally public synthetic-only values. The
local DB owner is used for convenience, **not a hosted privilege model**. Auth,
invitation delivery and extraction remain unconfigured and fail closed. The HTTP
rehearsal checks packaging only: production Secure cookies/TLS, login, email,
consent and candidate journeys require separate integrated staging evidence.
Never inject real provider credentials into this rehearsal.

Both runtime images use non-root users. API executes Uvicorn directly without
reload; web executes `next start` directly with Node. Compose uses an init
process and a 35-second stop window; Uvicorn drains for up to 25 seconds.
Platform ingress must stop admitting requests before container termination.
Definition files retain the repository layout required by the API; the shared
editable Python install points at source included in the runtime image. Web
keeps normal Next packaging and production npm dependencies, avoiding an
unapproved Next config change.

Base image tags and some Python transitive dependencies are not digest/hash
locked. Release preparation must record resolved base/image digests, Python
inventory and vulnerability scan results; a revision label alone does not make
future rebuilds byte-identical. Promote the **same image digests** between
stages. Do not provide secrets as build arguments or copy environment files into
images.

## Hosted configuration still to implement and rehearse

| Boundary           | Required configuration / evidence                                                                                                                                                                                                                                                                                                                                                                                 |
| ------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Hosting decision   | Record accountable owner, vendor, region, staging/prod isolation, public origin, image registry, immutable revision/digest, release permissions and costs before provisioning.                                                                                                                                                                                                                                    |
| TLS ingress        | Terminate TLS with managed certificate renewal and HTTP redirect; expose only web, preserve streaming, cap request size/time/rate, redact candidate paths/tokens, verify Secure cookies and same-origin proxy behavior.                                                                                                                                                                                           |
| Private API        | Route server-only `API_BASE_URL` to private API DNS; API has no public listener. Restrict network access to web, controlled jobs and probes; configure trusted forwarded headers only for actual proxies. Local loopback API publication is rehearsal-only.                                                                                                                                                       |
| Managed PostgreSQL | Private network, encrypted storage/backups and verified TLS (`sslmode=verify-full` plus trusted CA), connection/pool budget and independent staging DB. Never use the local Compose DB for hosted data.                                                                                                                                                                                                           |
| DB roles           | Migration identity owns schema and DDL; runtime identity has only required DML/sequence/schema usage, no ownership/superuser/role creation/DDL/trigger-disabling privileges. Preserve audit immutability; review exact grants against migrations and verify denied mutation paths in staging. Inject migration URL only into the migration job.                                                                   |
| Secrets            | Use platform secret injection for `DATABASE_URL`, `AUTH_JWT_SECRET`, issuer/audience and `INVITE_TOKEN_SIGNING_SECRET`; configure candidate HTTPS origin and approved privacy/contact copy. Extraction key is optional until configured-provider tests. Delivery adapter/provider remains a separate package; no env variable alone enables it here. Disable synthetic login in hosted mode after 6A integration. |
| Readiness          | `/health` is process liveness only. Gate traffic on explicit DB connectivity, expected Alembic head and compatible definitions; 11B owns application readiness/configuration validation. Missing auth/provider secrets do not currently prevent health success.                                                                                                                                                   |
| Jobs               | Schedule `python -m app.privacy.retention` in the API image only after approved policy, least-privilege credentials, non-overlap, timeout, retry and missed-run alerts are configured. 10C/11C retain backlog/replay/monitoring gates.                                                                                                                                                                            |
| Scale              | Begin with an explicitly selected replica count; current in-memory rate limiting and Next cache/Server Action coordination require review before scaling. Restrict provider egress; do not infer readiness from a paid probe.                                                                                                                                                                                     |

## Controlled release and recovery procedure

1. Record clean source revision, image digests, migration head, definition and
   algorithm versions, configuration version and operator. Review additive
   schema compatibility with the prior release; serialize migration jobs. Take
   and verify an encrypted restore point according to the approved recovery
   objectives.
2. On isolated staging, run the API image once with the migration identity and
   `alembic upgrade head`. Check `alembic current`, then start API/web with the
   runtime identities. Do not seed automatically. Any synthetic fixtures must be
   separately authorized and restricted to the isolated staging database.
3. Verify schema/assets, restricted privileges, readiness, TLS/cookies, full
   synthetic journeys and graceful drain. Record evidence and stop criteria
   before promoting those exact digests. CI/registry/deploy automation is not
   provisioned.
4. For application rollback, first prove the previous image pair can read the
   **current** schema and historical definitions/reports in staging. Drain
   traffic, restore previous image digests/configuration, leave the schema/data
   intact, and repeat readiness and synthetic checks. Retain immutable old
   definitions.
5. If schema or interpretation is incompatible, stop the rollout and forward-fix
   with a reviewed additive migration/application release. Do not run
   `alembic downgrade`, erase the DB, or overwrite historical interpretation as
   a generic rollback. A destructive recovery requires a separately reviewed
   restore and deletion-replay plan (10C/11C), with actual RPO/RTO and data-loss
   authorization.

The local same-image restart is not a prior-release rollback or populated
upgrade rehearsal. Those, hosted TLS/private networking, managed DB and real
release gates remain pending; see `docs/implementation/11a-report.md` for actual
evidence.
