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

```bash
npm run setup
cp apps/web/.env.example apps/web/.env.local
cp apps/api/.env.example apps/api/.env
npm run db:up
npm run db:migrate
npm run db:seed
npm run db:verify
```

Run these commands from the repository root. `npm run setup` uses `npm ci` to
install the npm workspaces from the committed `package-lock.json`, creates
`.venv`, and installs the API and test dependencies. Set `PYTHON_BIN` if
`python3` is not the desired interpreter:

```bash
PYTHON_BIN=python3.12 npm run setup
```

## Run locally

Start both development servers:

```bash
npm run dev
```

The web app is available at <http://localhost:3000> and the API at
<http://localhost:8000>. Their machine-readable health endpoints are:

- Web: <http://localhost:3000/api/health>
- API: <http://localhost:8000/health>

Run either app independently with `npm run dev:web` or `npm run dev:api`.

The API launcher parses `apps/api/.env` as dotenv data; do not source it in a
shell. Values in that file override inherited environment variables, including
`API_HOST`, `API_PORT`, and `LOG_LEVEL`. If the file is absent, the launcher
uses the inherited values or defaults to `0.0.0.0`, `8000`, and `info`; empty
values also use those defaults. Shell commands and `${...}` references in values
are treated literally. Quote free-text values as shown in the example. If you
change the API port, update `API_BASE_URL` in `apps/web/.env.local` to match.

The example configuration can start both health endpoints without provider
credentials. Role extraction and invitation delivery need their provider setup
before those features can be used. Invitation email uses Resend and a durable
encrypted queue; follow
[delivery setup and recovery](docs/invitation-delivery.md) and schedule
`npm run invitations:deliver` to process committed work.

Internal users sign in through Auth0 Universal Login. Configure the provider,
bootstrap the first administrator, and provision recruiter/manager accounts
using [the identity setup and operations guide](docs/identity.md).
Administrators manage access in the browser's **Accounts** workspace. The pilot
intentionally supports one organization per provider account.

The same-origin browser proxy keeps API credentials in an HTTP-only session
cookie and checks mutation origins. Sessions expire with the provider token or
after eight hours, whichever comes first. The header shows account/organization
context and sign-out. The example configuration starts health endpoints without
provider credentials; actual sign-in requires Auth0 setup.

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
