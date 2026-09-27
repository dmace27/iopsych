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
profile drafts. Recruiters, hiring managers, and administrators can revise the
latest draft. A profile revision creates a new immutable snapshot; it never
overwrites prior construct ratings. Only a hiring manager can approve the latest
draft. Approval activates the role, freezes that version for API editing, and
supersedes the previously approved version. Archived roles remain readable for
history but reject further writes.

Every profile draft must contain all six version-one constructs. Later PATCH
requests may change a subset, but still create a complete copied version.
Evidence excerpts must occur verbatim in the role's job description, and the
description is locked once profile versioning begins so historical evidence
remains traceable.

## Candidate invitations and consent

Package 2B adds recruiter invitation creation at
`POST /v1/roles/{role_id}/invites`, revocation below that resource, and
token-scoped candidate landing and consent routes below
`/v1/candidate/invites/{token}`. Invitations can target only an approved role
profile in the authenticated organization. Candidate links expire, can be
revoked immediately, and are rate-limited independently from internal-user
actions.

Invite tokens contain 32 random bytes plus an HMAC signature. Only a SHA-256
fingerprint is stored; neither API responses nor audit metadata include the raw
token, and the Uvicorn access logger redacts candidate token path segments.
Email is rendered through a narrow delivery interface that accepts no assessment
questions, responses, or scores. The default adapter fails closed without
logging the link, so a hosted deployment must install a transactional email
adapter explicitly.

Consent is an explicit `consent` or `decline` decision tied to a versioned
notice. A decision is terminal for its invitation, repeated identical requests
are idempotent, and only affirmative consent makes `can_start_assessment=true`.
Assessment code must call the shared `require_consented_invite` gate before
creating or updating candidate work. Configure the signing key, candidate URL,
expiry policy, rate limits, notice version, and privacy/accommodation contacts
using the `INVITE_*` settings shown in `.env.example`.
