# Package 4C threat model

Reviewed 2026-09-30. Scope: existing consented, human-reviewed MVP only. No
ranking, employment decisions, integrations, or new account flows are added.

## Assets and trust boundaries

Assets are internal bearer JWTs/session cookies, candidate invitation
credentials, candidate PII and responses, approved profile versions, reports,
and audit events. Untrusted parties include anonymous clients, other tenants,
candidates, and users with insufficient roles. Job descriptions and
extraction-provider output are untrusted even when submitted by an authenticated
recruiter.

Browser → Next routes → FastAPI → tenant-scoped SQLAlchemy services → database.
The browser authenticates internal requests with an HTTP-only cookie; Next sends
only the configured upstream a bearer header. FastAPI does not authenticate with
cookies. Candidates use scoped signed invitations whose stored representation is
a hash. Email delivery and extraction providers are separate external
boundaries. Hosting ingress, log collectors, backups, and secret storage are
operational boundaries outside this repository.

## Threats, controls, and disposition

| Flow / threat                                                              | Control and evidence                                                                                                                                                                                                                                            | Disposition                                                                                           |
| -------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| Role/profile ID guessing, cross-tenant reads or writes                     | Database-authoritative tenant/RBAC checks, non-disclosing 404s; `test_authorization.py`, `test_roles_api.py`                                                                                                                                                    | Resolved in application                                                                               |
| Recruiter approves a role, or approved evidence changes                    | Hiring-manager approval gate, immutable profile versions; role API regression tests                                                                                                                                                                             | Resolved in application                                                                               |
| Job-description injection or fabricated extraction evidence                | Schema/evidence validation and draft-only provider results; `test_role_extraction.py`; mandatory approval remains                                                                                                                                               | Resolved at application boundary; human review remains necessary                                      |
| Report generated before consent, submission, or approval                   | Report service guards; `test_reports.py`, `test_reports_postgres.py`; evidence and algorithm version persisted                                                                                                                                                  | Resolved in application                                                                               |
| Report disclosure through browser/proxy caches                             | API middleware, session routes and web proxy use `no-store` even on unhandled errors; no-referrer policy on web and API                                                                                                                                         | Resolved in application responses; ingress must preserve headers                                      |
| Cross-site sign-in, logout, candidate submission, or internal mutation     | Same-origin Origin/Fetch Metadata checks; strict SameSite HTTP-only cookie with production `__Host-` prefix; production Secure flag; eight-hour maximum browser cookie lifetime; existing session/proxy tests                                                   | Resolved for browser cookie authentication; JWT expiry remains authoritative                          |
| Script injection and framing                                               | Per-request nonce CSP with dynamic rendering, no production eval, no external scripts, no objects, no framing, same-origin form action; proxy test and production HTTP verification                                                                             | Resolved for scripts/framing; inline styles explicitly accepted below                                 |
| Invite guessing, expiration bypass, revocation bypass, repeated submission | Signed expiring tokens, hashes at rest, consent gate, lifecycle checks and one-time submission; invitation/report tests                                                                                                                                         | Resolved in application                                                                               |
| Anonymous or authenticated request bursts                                  | 300 requests/minute per direct API peer before auth/database; bounded 10,000-key limiter fails closed on capacity; existing invite limits remain; 429 and Retry-After preserved by sign-in and both web proxies; security unit tests and production smoke check | Resolved for one process; distributed denial of service accepted only for local/synthetic pilot below |
| Invite/JWT disclosure in routine logs                                      | Process-wide Python record factory redacts candidate paths, interpolated Bearer strings, secret-labelled values, email addresses, and exception/stack text, including future child loggers; redaction tests; never log request bodies                           | Resolved for covered application loggers; infrastructure logs require deployment action               |
| Committed secrets and vulnerable dependencies                              | Full-history Gitleaks, exact public fixture exception, npm audit high/critical gate, strict pip-audit installed graph gate in Security workflow                                                                                                                 | Resolved in CI configuration; hosted execution must be verified                                       |

## Explicitly accepted implementation limits

These are engineering decisions for a local/synthetic pilot, not privacy/legal
approval or permission to launch with real candidate data.

- Public Swagger/Redoc schema pages retain frame denial and no-store but are
  exempt from the JSON API deny-all CSP so their existing UI assets still load.
  They expose schema only; application routes use the restrictive policy. Owner:
  engineering.
- Inline **styles** remain allowed for existing framework/UI compatibility.
  Inline scripts require a nonce, and production eval is blocked. Revisit if the
  application adds untrusted HTML or user-provided styling. Owner: engineering.
- Rate counters are process-local and reset on restart. The Next browser proxy
  shares an upstream peer budget. The development launcher and smoke test use
  `--no-proxy-headers`; production must also use that setting for direct-peer
  budgets, or explicitly configure and restrict a trusted ingress. The app must
  never trust client-controlled forwarding headers. Multiple API workers and
  distributed attacks need a shared ingress limiter. Set ingress per-client and
  per-account limits, connection/body-size/timeouts, and restrict direct API
  access before a hosted pilot. Owner: engineering.
- JWTs remain provider bearer credentials. Cookie lifetime is bounded, but there
  is no new server-side session revocation system. Provider expiry, active-user
  checks, secret rotation, and existing authorization remain in force. A stolen
  valid token remains usable until expiry/revocation. Owner: engineering.
- Candidate links remain in URLs, so browser history, email forwarding, and
  endpoint/reverse-proxy access logs can expose them. App responses suppress
  referrers and caching; configure all infrastructure logs to redact candidate
  path segments, avoid analytics on those pages, and never record payloads,
  cookies, Authorization, PII, or exports. The Python log record factory
  sanitizes messages and exception text before handlers, but arbitrary
  structured extras, third-party telemetry and captured exception locals require
  their own allowlist. Owner: engineering/operations.
- TLS termination/HTTP redirects, database and backup encryption, managed secret
  injection, log access controls, and audit database privileges are deployment
  responsibilities. Web production responses include HSTS without preloading or
  assuming control of subdomains. Verify these controls before any hosted pilot.
  Owner: engineering/operations.
- Dependency scans detect known advisories, not all malicious packages. npm
  blocks high/critical advisories; pip-audit blocks all reported advisories. No
  advisory suppression is configured. The one secret exception matches only
  `privacy-invite-test-secret-with-at-least-32-bytes`, a public synthetic test
  key, and must never be used for deployment. Owner: engineering.

## Revalidation

Run the check/build/security workflows on every PR. Production smoke tests
exercise the existing role/profile and candidate/report flow with synthetic data
in an isolated PostgreSQL schema, and are required after the production build.
Revisit this model when changing authentication, proxy trust, token delivery,
report guards, logging, HTML rendering, providers, or deployment topology.
Rotate any genuine leaked credential before considering a scanner exception; an
exception is not rotation.
