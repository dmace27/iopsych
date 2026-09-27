# IOPsych API

The API is a Python 3.12+ FastAPI application. From the repository root, install
its dependencies with `npm run api:install`, start it with `npm run dev:api`,
and run its tests with `npm run test:api`.

Interactive OpenAPI documentation is available at <http://localhost:8000/docs>
while the service is running.

Database models live in `app/database`, and the schema is managed exclusively
through Alembic. From the repository root, use `npm run db:migrate`,
`npm run db:seed`, and `npm run db:verify`. The verification command checks that
the two synthetic seed organizations cannot read one another's users, roles,
profiles, or audit data through the organization-scoped access layer.

Internal API routes accept provider-issued HS256 bearer JWTs. The token must
contain `sub`, `organization_id`, `iss`, `aud`, and `exp` claims; the configured
issuer, audience, and secret are documented in `.env.example`. Roles always come
from the current database user rather than token claims, and organization
lookups use the verified token tenant plus the scoped repository. Sensitive
endpoints marked with `@audited(...)` append an immutable audit event for
successful, rejected, and failed authenticated requests.

## Role and profile lifecycle

Package 1B exposes organization-scoped role CRUD at `/v1/roles` and versioned
profiles below `/v1/roles/{role_id}/profiles`. Recruiters and explicitly
authorized administrators can create, update, and archive roles and can create
or revise profile drafts. A profile revision creates a new immutable snapshot;
it never overwrites prior construct ratings. Only a hiring manager can approve
the latest draft. Approval activates the role, freezes that version for API
editing, and supersedes the previously approved version. Archived roles remain
readable for history but reject further writes.

Every profile draft must contain all six version-one constructs. Later PATCH
requests may change a subset, but still create a complete copied version.
Evidence excerpts must occur verbatim in the role's job description, and the
description is locked once profile versioning begins so historical evidence
remains traceable.
