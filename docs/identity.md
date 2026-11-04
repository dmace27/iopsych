# Internal identity and account operations

The first pilot uses **Auth0 Universal Login**, one configured issuer, and one
organization per internal account. It does not implement organization switching
or automatic email-based enrollment. Candidate invitation access is separate.

The browser uses an authorization code flow with PKCE (`S256`), state and nonce.
`openid-client` handles discovery and protocol validation, with signed ID-token
verification enabled. A ten-minute encrypted, HTTP-only, SameSite=Lax
transaction cookie holds the verifier and safe return path. The callback
exchanges the code on the server, asks FastAPI to authorize the account, and
establishes the existing HTTP-only, SameSite=Strict session cookie. Production
cookies require HTTPS and use `__Host-` names. Session lifetime is the smaller
of the provider token's remaining lifetime and eight hours. No refresh tokens
are requested or retained.

FastAPI uses PyJWT and the issuer's HTTPS JWKS endpoint to verify **RS256 API
access tokens**, exact issuer, API audience, expiry, issue time and subject. Key
sets are cached for five minutes, unknown key IDs trigger refresh, and provider
requests have five-second timeouts. Claims cannot assign application permissions
or organizations. Every API request resolves the globally unique provider
subject to the current database user and checks its active state and role. The
HMAC verifier remains available only as a separately configured development/test
mode; Auth0 mode never falls back to it.

## Configure an Auth0 tenant

1. Create an Auth0 **Regular Web Application**. Use Universal Login and the
   authorization code grant with `client_secret_post` token endpoint
   authentication. Configure ID-token signing as RS256.
2. Register a custom API with identifier `iopsych-api` (or another exact value
   shared by both apps), RS256 signing, and a short access-token lifetime, for
   example 15 minutes. This application uses its own database roles rather than
   Auth0 role claims. Disable public signup for the controlled pilot; create
   accounts or send account setup invitations through Auth0's administrator
   dashboard. Enable the tenant's MFA policy as appropriate to the pilot.
3. Set the exact Allowed Callback URL to
   `http://localhost:3000/api/auth/callback` locally or
   `https://YOUR-WEB-HOST/api/auth/callback` for staging/production. Use
   separate provider applications and secrets for separate environments. Do not
   allow wildcard callbacks.
4. In `apps/web/.env.local`, set `APP_BASE_URL` to the web origin,
   `AUTH0_ISSUER` to `https://YOUR-TENANT.auth0.com/`, `AUTH0_CLIENT_ID`,
   `AUTH0_CLIENT_SECRET`, and `AUTH0_AUDIENCE` to the custom API identifier.
   Generate `AUTH_SESSION_SECRET` with `openssl rand -hex 32`. Web replicas must
   share this secret. Supply hosted secrets through the deployment secret store.
5. In `apps/api/.env`, set `AUTH_PROVIDER=auth0`, `AUTH_JWT_ISSUER` to the same
   exact issuer, and `AUTH_JWT_AUDIENCE` to the same API identifier. No HMAC
   secret is needed. Leave `ENABLE_TOKEN_SIGN_IN=false` in the web environment.
6. Apply `npm run db:migrate`, through the canonical integration head (`20261104_0012`), then restart
   both apps. Health checks work without a provider account. Missing web
   settings show actionable sign-in configuration feedback instead of accepting
   tokens.

Use one hostname consistently. `localhost` and `127.0.0.1` have different
cookies and callback origins. Hosted `APP_BASE_URL` must use HTTPS. Reverse
proxies must route the callback unchanged and must redact callback query strings
(which carry one-time authorization codes), cookies, authorization headers and
response bodies from access logs and telemetry. Provider errors are never
reflected in application URLs or logs by the callback implementation.

## Bootstrap the organization and first administrator

An operator with database access performs this **once per new organization**.
Create the administrator in Auth0 first and copy its exact User ID (`auth0|...`,
or the full subject for the configured connection); do not substitute an email.

```bash
cd apps/api
../../.venv/bin/python -m app.auth.bootstrap \
  --slug pilot-organization \
  --organization-name 'Pilot Organization' \
  --subject 'auth0|COPY-EXACT-USER-ID' \
  --email 'admin@your-organization.example' \
  --name 'Pilot Administrator'
```

The command creates the organization, administrator and audit event in one
transaction. It refuses an existing organization and cannot overwrite its users
or roles. The database connection uses the same dotenv configuration as the API.
Do not use the synthetic seed as production account provisioning.

The administrator then signs in normally, opens **Accounts**, and provisions
recruiters/managers using their exact Auth0 User IDs, names, emails and explicit
application permissions. Creating an application account does not create or
email a provider account: the administrator first completes account setup in
Auth0. Recruiters and managers subsequently sign in independently and perform
only their permitted tasks without handling JWTs or editing the database.

Accounts lists are tenant-scoped and paginated at 50 rows. The administrator can
change another user's role or active state. Deactivation and role changes apply
on that user's next API request, including requests from an existing browser
session. Changes and rejected actions are audited with the domain transaction.
Self-deactivation/demotion is prohibited; ask another administrator to make that
change. Tenant account mutations lock the organization and recheck the actor
after acquiring the lock, preventing two administrators from concurrently
removing each other's access based on stale authorization.

## Session expiry, sign-out and revocation

The header shows account name, role, organization and **Sign out**. Sign-out
clears the application session and pending login transaction. The provider's SSO
session is separate; each new app login uses `prompt=login` so a shared device
cannot silently resume the previous user's provider session. Expired API
credentials are removed by the proxy and the workspace/header offers sign-in
recovery. Supported local `returnTo` paths are restricted to roles, reports,
privacy and accounts; external URLs and authentication loops are rejected.

Auth0 JWTs are self-contained. Blocking a provider account or revoking a
provider session does not invalidate an already issued API access token
immediately. **Disable the application account as well** for immediate
application denial, then block/reset it in Auth0 as required. Sign-out only
clears this browser; it does not revoke copied bearer tokens. Re-enabling a
disabled application account allows its otherwise-valid tokens again until their
expiry. For a compromised account, keep it disabled until all issued access
tokens have expired before re-enabling it. No claim of immediate provider-wide
JWT revocation is made.

## Verification and release evidence

Automated tests run discovery, code exchange, signed ID-token/JWKS validation
and API authorization against a simulated provider HTTP contract. They cover
state and nonce failures, missing/tampered/expired transactions, provider denial
and outages, API rejection, safe redirect handling, transaction consumption,
actual RSA access-token signatures, incorrect issuer/audience/algorithm,
missing/expired claims, signing-key rotation, disabled users, fresh role
changes, tenant isolation, account uniqueness, audit attribution, bootstrap and
permission enforcement. Browser component tests cover provision/update controls,
pagination, sign-out failures and expiry recovery. Migration tests preserve
existing users as active.

**Live-provider acceptance remains a deployment gate.** No Auth0 tenant
credentials are committed or supplied by this implementation. Before closing
Task 3:

- Configure an actual Auth0 tenant and controlled administrator, recruiter and
  manager accounts using the steps above.
- In an HTTPS staging browser, sign in separately as recruiter and manager;
  create/review a role and exercise the different permissions. Confirm the API
  rejects an unprovisioned provider account.
- Confirm safe return to a report, provider cancellation, session expiry,
  visible sign-out, account blocking plus application deactivation, permission
  changes with an existing session, and current/new signing keys after rotation.
- Record environment, callback origin, revision and results without credentials,
  tokens, cookies, authorization codes or personal data.

The existing deterministic production smoke opts into
`ENABLE_TOKEN_SIGN_IN=true` and `AUTH_PROVIDER=hmac` in its isolated child
environment. That smoke verifies application HTTP/session behavior; it is not
evidence of live Auth0 integration. The token exchange endpoint is unavailable
by default and has no browser form.

Local verification on November 3, 2026 passed `npm run check` with **478 tests
and zero skips**, using disposable PostgreSQL 16 for both the existing report
concurrency tests and the account migration/locking tests. API application
coverage remains 100%; `npm run build` and the PostgreSQL-backed production HTTP
smoke passed. The audit failure regression verifies that failed audit commits
roll back newly provisioned accounts, including with the SQLite test driver. A
fresh npm audit reports the same 25 advisories as the original lockfile and
workspace manifests (21 moderate, 3 high, 1 critical), with no advisory
targeting the added authentication libraries. These findings remain a release
gate; passing local tests does not resolve them or establish
hosted/live-provider evidence.

Provider contracts:
[Auth0 access-token validation](https://auth0.com/docs/secure/tokens/access-tokens/validate-access-tokens),
[openid-client](https://github.com/panva/openid-client),
[PyJWT JWKS usage](https://pyjwt.readthedocs.io/en/stable/usage.html#retrieve-rsa-signing-keys-from-a-jwks-endpoint).

## Reconciled account API

Existing `/v1/accounts/users` access management retains optimistic `expected_version`.
Provider `/v1/users` provisioning coexists; its PATCH also requires `expected_version`
and delegates the same tenant/user locking and version service. GET/POST responses
include `version`. See [collision ledger](implementation/remote-reconciliation.md)
for the migration mapping and unsupported remote-head database upgrade path.
