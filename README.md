# IOPsych MVP

Technical foundation for the consented, human-reviewed IOPsych pilot described
in [`mvp-spec.md`](./mvp-spec.md). This package contains infrastructure only: a
Next.js web shell, a FastAPI service, shared domain contracts, PostgreSQL data
models, and the developer quality gates.

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

`npm run setup` installs the npm workspaces, creates `.venv`, and installs the
API and test dependencies. Set `PYTHON_BIN` if `python3` is not the desired
interpreter:

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

## Database commands

```bash
npm run db:up       # Start PostgreSQL 16 and wait until it is healthy.
npm run db:migrate  # Apply all Alembic migrations to DATABASE_URL.
npm run db:seed     # Upsert two deterministic synthetic organizations.
npm run db:verify   # Verify seed completeness and cross-tenant read denial.
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
