# Remote provider reconciliation receipt

Reviewed November 4, 2026: local `b77567c0f749f75ef497691ce9a37a0a0d62a95a`
against adopted remote `646201a58ceaeb679900344319ea95fdb888641e`
(`origin/codex/fix-security-dependencies`). Read-only application review;
only this receipt changed. Read `apps/web/AGENTS.md` and the accelerated
execution schedule in `final-implementation-plan.md`. Orca terminal metadata
confirmed this isolated worktree and `GPT-6-Astra medium fast` session.

Evidence below is source code at those revisions, not provider research or a
claim that hosted services were exercised. No credentials, external provider
requests, real mail, database changes, full suite, push or deployment were used.

## Recommended adapter boundary

Adopt Auth0 verification/login and the Resend frozen-message outbox while
retaining the local API, immutable assignments, account concurrency and
explicitly synthetic SMTP queue. Separate delivery modes and storage ownership
are safer than renaming local fields into remote fields: both revisions define
`InvitationDelivery`/`invitation_deliveries` with incompatible constraints.
The reconciliation owner must allocate schema/migration changes. A distinct
provider outbox table/model is a straightforward option; a combined table needs
an explicit mode discriminator and mode-specific checks, not nullable fields
without invariants. Never have both workers consume the same job.

| Boundary | Primary evidence | Integration guidance |
| --- | --- | --- |
| Issuance request identity | Local `invitations/schemas.py`, `queue.py:issuance_digests`, web `lib/invitation-issuance-client.ts` and internal proxy; remote `schemas.py:InvitationCreateRequest`, `service.py:_issue` | Preserve the local 16–128 visible-ASCII `Idempotency-Key` contract. Remote requires a UUID `request_id` body field; local strict schema rejects it. Normalize once at the API boundary, retain tenant-scoped uniqueness and fingerprint conflict checks, and reject conflicting dual keys. For arbitrary existing header values use a documented deterministic UUID namespace mapping (or persist the digest directly); never generate a new random UUID on retry. For UUID headers use the UUID itself if supporting a matching body form. Fingerprint normalized business fields, role and replacement target, excluding transport key fields. |
| Replay outcome | Local `queue.py:replay_invitation`; remote `service.py:_issue` | Local rejects expired/revoked/cancelled/uncertain replay with `invitation_reissue_required`; remote returns the existing invite even when terminal. Preserve explicit local recovery errors and UI behavior. Keep durable request records so retry cannot silently mint new mail; new issuance requires an explicit new key. |
| Invitation versus delivery state | Both `database/models.py:AssessmentInviteStatus`; local `worker.py`, remote `service.py:_issue`, `outbox.py:_attempt` | Both invitation enums use `active`, not `sent`. Local stays `pending_delivery` until confirmed SMTP acceptance; remote creates `active` before provider send, allowing a delivered link to work after an acceptance/commit crash. Retain this intentional per-mode distinction. `sent`/`delivered` are delivery evidence, never consent. Keep `delivery_state` in local list/create/revoke responses and adapt the separate remote delivery endpoint for current UI. |
| Recovery semantics | Local `recovery.py:decide_delivery`; remote `outbox.py:process_delivery_batch` | Local SMTP ambiguity is terminal `uncertain`; never retry it automatically. Remote retries the exact frozen payload with `invite/{delivery.id}`, bounded by the original 23-hour deadline. Do not apply remote retry logic to SMTP or restart deadlines on worker restart. Map remote `retrying`, `reissue_required`, `failed`, `bounced`, `complained`, `delivered` explicitly in UI/contracts; do not reduce failures to `sent`. |
| Account mutation | Local `accounts/schemas.py`, `accounts/service.py:update_account`; remote `auth/users.py` | Keep `/v1/accounts/users`, keyset response, `version` and strict `expected_version`, organization-before-user locks, actor reauthorization, self-change prevention, last-admin check and audited before/after. Remote `/v1/users` PATCH lacks version checks and would bypass the stronger contract if enabled as a second write path. Adopt provisioning separately, sharing the local mutation discipline. |

## Auth0 and controlled login

Import remote `auth/auth0.py`, optional organization identity from `auth/tokens.py`,
and the subject-based lookup in `auth/dependencies.py`. Auth0 pins RS256,
issuer/audience and required claims; JWKS URL comes from configured issuer,
with a five-second timeout and 300-second key-set lifetime. Roles and tenant
must still come from a fresh active database user. Auth0 subject-only lookup
requires the global subject uniqueness invariant; HMAC identities must retain
their explicit organization match. Preserve inactive-user rejection.

Merge `AuthenticationSettings.provider` into local `auth/config.py`; do not
replace it. Local defaults are `environment="production"` and
`local_login_enabled=False`. Preserve `auth/local_login.py`, its exact seed
identity/loopback/origin checks and short-lived token, the web local session
route and launcher. Select one verifier explicitly: Auth0 configuration failure
must never silently fall back to HMAC. Disable synthetic token issuance when
Auth0 mode is selected, or otherwise make that incompatible configuration fail
closed; no default development or test bypass.

Remote `apps/web/lib/provider-auth.ts` supplies PKCE, state/nonce, encrypted
ten-minute transaction, a fixed configured callback origin, secure production
cookies, OIDC five-second timeout and five-second `/auth/me` validation. Keep
those properties. Preserve the local hardened return-to validator and sign-out
cookie-expiry behavior when adding remote login/callback routes and clearing the
transaction cookie. Remote `/api/session` adds `ENABLE_TOKEN_SIGN_IN` gating;
default-deny that manual route and explicitly opt in only synthetic browser
fixtures that need it. This flag must not disable the separately protected
`/api/session/local` route. Existing session/local fetches lack a timeout in both
or local source: add bounded fetches during integration rather than assuming the
new provider callback bounds all authentication paths.

## Encryption, cancellation and provider perimeter

- Local `credentials.py:LocalCredentialCipher` uses AES-256-GCM with authenticated
  organization/invite/delivery/expiry/key-ID context, separate-key checks and a
  15-minute queue credential lifetime. `queue.py:local_cipher` additionally
  requires development, synthetic definitions and loopback UI. Preserve it for
  SMTP. Remote `encryption.py` uses Fernet/MultiFernet for the complete frozen
  message, a previous-key rotation slot, 23-hour TTL and provider-credential
  fingerprint. It does not bind ciphertext to row identifiers like the local
  envelope. These formats are not interchangeable; add equivalent row binding
  to provider envelopes if combining their handling. Do not transplant local
  ciphertext into the provider decryptor or silently reissue undecryptable jobs.
- Remote `provider.py` fixes the HTTPS Resend endpoint, uses a 1–30 second
  configured timeout, caps response reads at 16 KiB, classifies 408/409/429 as
  retryable and suppresses sensitive error bodies. Retain frozen sender/content
  and provider key scope through retries. Its `urlopen` uses default redirect
  handling; an explicit no-redirect handler would make the fixed-endpoint
  credential boundary stronger. This is static hardening guidance, not an
  observed provider redirect.
- Remote `webhooks.py` verifies original bytes and timestamp with Svix before
  parsing, caps body at 64 KiB, deduplicates event IDs, correlates provider ID or
  signed delivery tag, locks invite before delivery, preserves status priority,
  and never revives cancelled/reissue-required rows. Retain the direct
  `/v1/webhooks/resend` ingress route and signatures without exposing a browser
  authenticated proxy bypass. Readiness must not call providers. Public URL/key
  validation and local runtime middleware must survive `main.py` integration.
- Remote `config.py` validates HTTPS candidate URLs outside loopback and forbids
  query/fragment, but does not explicitly reject URL userinfo. Add that check,
  preserve hosted validation and ensure the chosen public candidate origin/path
  matches the browser route. Encryption key validation checks Fernet shape;
  explicitly preserve independent-key policy rather than assuming format
  validation proves keys differ.
- Both services change invitation state on consent/decline. Remote
  `record_consent` does **not** immediately purge queued ciphertext; a later
  worker sees non-active status and cancels it. Call unified cancellation in the
  consent/decline transaction while holding the invite lock to remove stale
  pending credentials immediately. Consent must still preserve the local frozen
  assignment and current integration notice-snapshot work.
- Both privacy services cancel delivery during anonymization, but import
  different functions. A shared cancellation facade must purge both applicable
  stores on revoke, expiry, deletion and retention, preserving invite-before-job
  lock order, audit and atomicity. Remote cancellation only handles queued or
  retrying jobs; local clears ciphertext even for terminal jobs. Verify no
  retained ciphertext, late webhook resurrection or resend after deletion.
  Retain local export/deletion locking and restore replay; do not replace the
  privacy service with the remote snapshot merely to change its import.

## Dependency and verification receipt

Remote adds `PyJWT[crypto]==2.15.1`, `svix==2.9.1`,
`python-dotenv==1.2.3`, `jose==6.2.15`, `openid-client==6.8.9`.
Its web manifest also moves local Next/eslint-config-next `16.4.1` back to
`16.3.8` and Vitest/coverage `5.0.3` back to `5.0.2`. Preserve local security
updates while the designated dependency owner adds provider packages and
reconciles the lockfile. These are observed revision differences, not a new
vulnerability audit. Preserve runtime packaging, lint isort configuration and
existing scripts rather than replacing remote manifests wholesale.

This receipt was checked with `git diff --check`; source inspections used scoped
`git show`, `git diff`, `rg` and file reads. No application tests were run by this
reviewer. The implementation owner should reserve focused verification for:

1. Existing local-login negative cases and synthetic session/browser fixtures;
   mocked Auth0 wrong issuer/audience/algorithm, unknown subject, inactive user,
   malformed state and safe return-to; no real JWKS request.
2. Existing account version/race tests with both provisioned Auth0 and HMAC
   identities; prevent a second unversioned mutation route.
3. Header/body retry equivalence, mismatched dual keys, changed payload, same key
   in another tenant, terminal replay and reissue using a fresh explicit key.
4. Local uncertain-send behavior plus remote frozen-message retry, commit
   failure, deadline and credential rotation; populated migration preservation.
5. Signed webhook duplicate/out-of-order/late events, consent/decline and
   deletion racing a worker, immediate credential purge, immutable assignments
   and notice snapshot retention. Use isolated synthetic PostgreSQL only.

Critical guidance was sent directly to reconciliation dispatch
`ctx_9a9c76cc5c41` in messages `msg_6af87cc1c6bb` and `msg_0a2e751cbf01`.
Implementation, reconciled tests and hosted/provider acceptance remain with
their owners; this document is a source review, not those acceptance receipts.

## Subsequent authorized Auth0 web implementation

Coordinator message `msg_445ae8120c9a` expanded this dispatch after the review
to own Auth0 web/session/sign-in integration. API, manifests, account workspace,
header/layout and migrations remain with their existing owners. Review receipt
commit: `0588b71`. Separate remote baseline commit: `edd94ba` adds
`lib/provider-auth.ts`, its simulated-provider tests, `lib/return-to.ts`, and
`app/api/auth/{login,callback}/route.ts` without unrelated remote files.

The following compatibility commit preserves local synthetic login and the
strict existing accounts/roles/reports/invites return allowlist, defaults sign-in
to Auth0, keeps token-paste UI out of production, and gates manual session POST
behind explicit `ENABLE_TOKEN_SIGN_IN=true`. It retains protected root-cookie
expiry on sign-out and also clears the provider transaction cookie with matching
attributes. Both local and manual session upstream fetches now have five-second
timeouts. Provider error redirects are relative fixed paths, avoiding request
Host-derived destinations; PKCE/state/nonce, fixed callback origin and API
authorization remain as adopted. Provider cookie policy lives in the small
`lib/login-cookie.ts` module so logout does not load the OIDC SDK.

Validation: six focused test files, **150 passed** (provider-auth,
safe-return-to, sign-in page/form, session and local session); scoped ESLint
passed; `npm run typecheck --workspace @iopsych/web` passed after Next typegen.
An initial raw `tsc --noEmit` lacked generated `PageProps`; the standard command
resolved it. Generated `next-env.d.ts` changes were reverted. The first provider
test run exposed six test URL-construction failures after switching to relative
error redirects; adapting the test URL parser resolved them. No real provider
requests occurred: discovery, token, JWKS and API responses are mocked. Provider
packages were linked only in ignored node_modules from the dependency owner's
installation; no manifests/lockfiles were changed here.

Browser-owner handoff: existing production browser specs fill the manual token
field, which is intentionally absent from the production UI now. Their isolated
synthetic runner must explicitly enable the fixture session POST and establish
sessions through same-origin `/api/session` requests, then update sign-in/axe
expectations to provider navigation. This browser migration, full reconciled
checks and hosted Auth0 smoke remain unverified here and were reported to the
coordinator and reconciliation lead before completion.
