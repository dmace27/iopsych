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

`POST /v1/roles/{role_id}/extract-profile` sends only the role title,
department, location, and job description through the configured structured
extraction provider. The provider is constrained by the shared JSON Schema and
the server independently validates every returned field, all six unique
constructs, the mandatory `needs_human_review=true` flag, and every verbatim
evidence excerpt. Invalid or unavailable provider responses are retried within
the configured bound and never create a partial profile. Validated assumptions
are stored with the immutable profile version for review. Successful extraction
creates a normal `draft`; only the existing hiring-manager-only approval route
can activate it. Configure the adapter and retry policy with the
`ROLE_EXTRACTION_*` settings in `.env.example`.

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

## Package 3B: persisted reports

Apply migration `20260927_0005` before using the new endpoints.

- `POST /v1/candidate/invites/{token}/submit` accepts the shared
  `AssessmentResponseSet` contract. The server checks the token and affirmative
  consent, scores all six answered/skipped blocks, and stores the definition,
  responses, scores, consent reference, and submission time. Identical retries
  return the same `assessment_id`; attempts to change a submission return 409.
  The candidate response contains only that score-free receipt. The invitation
  landing response also includes a nullable `assessment_id` so another device
  can recognize an existing server submission.
- `POST /v1/reports` accepts `assessment_id` and `role_profile_id`. The
  assessment must belong to the authenticated organization, be submitted and
  consented, and reference the invitation's human-approved profile version.
  Scores and approval cannot be supplied by the caller. Identical requests
  return the existing snapshot, protected by a unique input/algorithm
  constraint.
- `GET /v1/reports/{report_id}` returns the stored report to internal
  recruiters, hiring managers, and admins in the owning organization.
  Cross-tenant IDs return the same 404 as unknown IDs.
- `GET /v1/roles/{role_id}/assessments?limit=50&offset=0` lists submitted
  assessment IDs, invite IDs, candidate email, profile ID/version, submission
  time, and existing report ID within one organization. Ordering is
  chronological; scores and classifications are excluded. `limit` is bounded to
  1–100.

Reports preserve profile version, assessment/scoring versions, algorithm
version, six independent classifications, role evidence, candidate response
summaries, rule explanations, confidence/uncertainty, and stable
interview-question IDs and text. No composite score or ranking is produced.
Report creation and its audit record commit together; generation requests and
report reads use audit middleware. Invitation expiry after submission does not
invalidate a historical report. A superseded profile remains eligible if its
human-approval timestamp and actor are present; superseded unapproved drafts
remain ineligible. Report and discovery responses use `Cache-Control: no-store`.

The existing candidate screen now submits through the same-origin API boundary
and shows completion only after server acknowledgement. Drafts stay on the
device; network failures preserve responses and allow retry. Older browser-only
completions are reopened for review and server submission. The internal proxy
permits report generation and reads, preserving its session-cookie and CSRF
protections.

### 3C recruiter report UI

Open a role profile and select **View recruiter reports** to reach
`/roles/{role_id}/reports`. Submitted sources appear in chronological order,
with pagination and the exact invited profile version. Generate a report from an
eligible submission or read its saved snapshot; `/reports/{report_id}` is the
authenticated permalink.

The UI validates the complete report envelope and shared matching schema before
rendering six independent construct cards. Each card shows role demand,
candidate response, classification, confidence, uncertainty, and an evidence
drawer with quoted role evidence, rationale, response counts, and comparison
rule. Structure's inverse comparison is explained explicitly. The guide shows
the approved primary and follow-up questions and stable reference IDs. Source
and algorithm versions remain inspectable, and the responsible-use warning stays
above the comparisons. No composite score, ranking, or disposition control is
present.

Native modal dialogs provide keyboard focus containment, Escape dismissal, and
focus return. Loading, empty, expired-session, inaccessible-report, and retry
states are covered by component tests, including stale requests after a role
change and pagination failures.

### 3C API handoff

1. Load `/api/internal/roles/{role_id}/assessments` to discover submitted
   sources.
2. If `report_id` exists, read `/api/internal/reports/{report_id}`. Otherwise
   post `{ "assessment_id": "...", "role_profile_id": "..." }` to
   `/api/internal/reports`, using the profile ID from the submission record.
3. Display the response's six `result.items` plus `usage_warning`. Each item has
   `construct_key`, `classification`, `confidence`, `explanation.role`,
   `explanation.candidate_response`, `explanation.applied_rule`,
   `explanation.uncertainty`, and `interview_questions.primary/follow_up` with
   stable `id` and `text`. Use the existing shared `MatchingResultSchema` for
   the `result` payload. The envelope also includes IDs, `role_profile_version`,
   and `generated_at`.

Errors use the existing problem-detail contract: 401 unauthenticated, 403 role
denied, 404 unknown/cross-organization resource, 409 lifecycle/input-pair
conflict, and 422 invalid request. Generation is idempotent and returns 201 for
both a new report and an identical retry. GET reads always return the stored
explanation.

## Package 4B: data rights and retention

Apply migration `20260929_0007` before using the privacy controls. Candidate
submissions freeze a `retention_expires_at` deadline using
`PRIVACY_RETENTION_DAYS` (90 days by default). Pre-migration submissions without
a stored deadline use their submission time plus the current configured period.
Candidate-facing disclosure copy comes from `INVITE_RETENTION_STATEMENT`, which
must contain the `{retention_days}` placeholder so the notice always reflects
the enforced duration.

Organization administrators can use the authenticated privacy workspace at
`/privacy` or call these tenant-scoped routes:

- `POST /v1/candidates/{assessment_id}/export` creates a no-store JSON export
  containing the retained invitation, consent, response/score snapshots, derived
  reports, and candidate-scoped activity.
- `DELETE /v1/candidates/{assessment_id}` irreversibly anonymizes the invitation
  email and token, revokes candidate access, erases assessment payloads, and
  deletes derived reports. The non-identifying consent/timing tombstone and
  immutable audit history remain. Repeated requests are safe and idempotent.
- `GET /v1/privacy/status` summarizes active, due, and anonymized records.
- `GET /v1/privacy/audit-events` reads bounded, newest-first tenant audit
  history, with optional exact `entity_id` and `event_type` filters. Pass the
  last returned event ID as `before` for stable cursor pagination.
- `POST /v1/privacy/retention/run` processes one tenant-scoped batch due for
  anonymization.

Run `npm run privacy:retention` from the repository root on a deployment
scheduler. The scheduler processes at most `PRIVACY_RETENTION_BATCH_SIZE`
records across organizations per invocation and prints only a non-identifying
count. Export, deletion, status, audit lookup, and manual retention requests all
append immutable audit events. An anonymized assessment is excluded from report
discovery and cannot be exported or used to generate a new report.

`npm run check` runs browser, API, contract, migration, and negative-path tests.
The PostgreSQL concurrency regression runs automatically with PostgreSQL
`DATABASE_URL` in CI, or locally with `TEST_POSTGRES_URL` set. It creates and
removes an isolated random schema, tests four simultaneous submissions and four
simultaneous report requests, and verifies one snapshot plus its creation audit.
