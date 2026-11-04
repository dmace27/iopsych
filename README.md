# IOPsych MVP

Implementation of the consented, human-reviewed IOPsych pilot described in
[`mvp-spec.md`](./mvp-spec.md). The current phase includes role-profile
authoring and human approval, candidate invitation/consent/assessment,
deterministic reports, structured draft extraction, and administrator
data-rights and retention controls. Shared contracts, tenant authorization,
PostgreSQL models, and automated quality gates cover the end-to-end workflow.

## Prerequisites

- Node.js 22 (see `.nvmrc`)
- npm 10 or newer
- Python 3.12–3.14 (the supported baseline is recorded in `.python-version`)
- Docker with Compose support for the local PostgreSQL 16 database

The API unit tests use SQLite and do not require Docker. Local development and
the integration verification use PostgreSQL 16.

## First-time setup

The commands below use a dedicated Compose project `iopsych-6a`, database
`iopsych_6a`, and loopback ports 5541 (PostgreSQL), 8101 (API), and 3101 (web).
They do not use or reset an existing database on port 5432. Run from the
repository root:

```bash
PYTHON_BIN=python3.12 npm run setup
cp apps/web/.env.example apps/web/.env.local
cp apps/api/.env.example apps/api/.env
npm run db:up
npm run db:migrate
npm run db:seed
npm run db:verify
```

`setup` runs `npm ci` against the committed lockfile, creates `.venv`, and
installs pinned direct API/test dependencies. The equivalent saved setup is
`npm ci && PYTHON_BIN=python3.12 npm run api:install`. Python transitive
requirements are not yet locked. Node 22 is the baseline; Node 24 is also
supported by the declared engines. Never source a dotenv file as shell code. The
API launcher parses it as data and preserves exported environment overrides.

## Run locally and sign in with synthetic data

For this local-only demonstration, set `AUTH_LOCAL_LOGIN_ENABLED=true` in
`apps/api/.env` and `LOCAL_LOGIN_ENABLED=true` in `apps/web/.env.local`. Keep
`AUTH_ENVIRONMENT=development`, the loopback API host, and the matching
`AUTH_LOCAL_WEB_ORIGIN=http://127.0.0.1:3101`. The template signing key is
local-only; replace it with a random key in your ignored file if sharing the
machine. Never use these settings or the template keys in a hosted environment.

```bash
npm run dev
```

Open <http://127.0.0.1:3101/sign-in>, choose **Alpha Recruiter** or **Beacon
Manager**, and select **Continue to roles**. The server exchanges that fixed
synthetic identity for a 15-minute HTTP-only, SameSite=Strict cookie; no JWT
editing or token pasting is needed. Each identity sees its own seeded tenant.
The API rejects arbitrary identities and mismatched seed records. Local login is
disabled by default, requires explicit development mode, and rejects nonloopback
hosts/peers/origins. Do not expose either development server through a tunnel or
reverse proxy. This is not provider authentication or pilot approval.
Invitations remain fail-closed without a delivery adapter; this setup sends no
email and does not call extraction providers.

With both apps running, verify the actual cookie session, tenant isolation, and
sign-out without printing credentials:

```bash
.venv/bin/python scripts/verify-local-login.py
```

Set `LOCAL_WEB_ORIGIN` and `LOCAL_API_ORIGIN` for this verifier if you changed
ports. It only accepts loopback HTTP origins.

Health endpoints: <http://127.0.0.1:3101/api/health> and
<http://127.0.0.1:8101/health>. Run apps separately with `npm run dev:web` or
`npm run dev:api`. Exported `API_HOST`, `API_PORT`, `LOG_LEVEL`, `WEB_HOST`, and
`WEB_PORT` override defaults; update `API_BASE_URL` in the web dotenv file and
`AUTH_LOCAL_WEB_ORIGIN` in the API dotenv file to match any port changes. For a
different database port, export `POSTGRES_PORT` when running Compose and update
`DATABASE_URL` to match before migration, seed, or verification.

```bash
# Actual launcher regression binds API 8101: stop the dev API first.
.venv/bin/python -m pytest apps/api/tests/test_launcher.py --no-cov
```

If Docker is unavailable, start Docker Desktop and retry `npm run db:up`. If a
reserved port is occupied, select a free port explicitly; do not stop an
unrelated service. `db:verify` must report two isolated organizations before
using synthetic login. A missing seed/policy produces an error on sign-in.

## Database commands

```bash
npm run db:up       # Start PostgreSQL 16 and wait until it is healthy.
npm run db:migrate  # Apply all Alembic migrations to DATABASE_URL.
npm run db:seed     # Upsert two deterministic synthetic organizations.
npm run db:verify   # Verify seed completeness and cross-tenant read denial.
npm run privacy:retention # Run one bounded cross-tenant retention batch.
npm run db:down     # Stop local containers without deleting database data.
```

The default `DATABASE_URL` is documented in `apps/api/.env.example` and matches
`compose.yaml`. Seed identities use the reserved `.example.invalid` domain; no
real candidate or employee information is included. Alembic migrations are the
source of truth for database creation—application startup does not create tables
automatically.

## Quality and test commands

```bash
npm run format          # Format JavaScript, TypeScript, JSON, Markdown, YAML, and Python.
npm run format:check    # Verify formatting without changing files.
npm run lint            # Run ESLint and Ruff.
npm run typecheck       # Run TypeScript and mypy checks.
npm test                # Run Vitest and pytest.
npm run build           # Build the shared package and production web bundle.
npm run check           # Run every non-build CI quality gate.
```

GitHub Actions applies migrations to an empty PostgreSQL 16 service, runs the
seed and tenant-isolation verifier, then runs `npm run check` and
`npm run build` for pushes to `main` and pull requests. Future packages should
extend these commands rather than introduce separate, undocumented quality
gates.

## Repository layout

```text
apps/
  api/       FastAPI application and Python tests
  web/       Next.js application and TypeScript tests
packages/
  shared/    Versioned TypeScript, JSON Schema, Pydantic, and fixture contracts
scripts/     Reproducible local setup scripts
```

Security hardening, deployment limits, and package 4C verification are
documented in [the threat model](docs/security/threat-model.md) and
[CI evidence](docs/security/ci-evidence.md).
