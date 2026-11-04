# Invitation email delivery and recovery

The pilot uses **Resend** for transactional invitation email. The API commits an
invitation, an encrypted delivery row, and the issuance audit together. A
separate bounded worker reads only committed work and sends email. Application
startup does not start an unreliable in-process background queue.

Delivery state is separate from consent/link state. A newly issued invitation is
`active` with `sent_at=null`; this means its link is valid when received. It
does not mean email has been sent. The raw token exists only transiently while
issuing or sending and inside an authenticated encrypted queue payload. The
invitation row stores its SHA-256 token hash. API responses, webhook records,
audit metadata and worker output never include the token or encrypted payload.

## Configure Resend and the worker

1. In Resend, add a sending domain and complete its DNS verification. Choose one
   verified sender mailbox. Disable click and open tracking for this domain so
   bearer links are not rewritten or collected as engagement data. Use separate
   provider applications/credentials for staging and production.
2. Create a sending API key restricted to the chosen domain where supported.
   Configure these **server-only** values in the API and worker environments:

   ```dotenv
   INVITE_DELIVERY_PROVIDER=resend
   INVITE_DELIVERY_API_KEY=YOUR-RESEND-SENDING-KEY
   INVITE_DELIVERY_FROM_EMAIL=invitations@YOUR-VERIFIED-DOMAIN
   INVITE_DELIVERY_ENCRYPTION_KEY=YOUR-FERNET-KEY
   INVITE_DELIVERY_TIMEOUT_SECONDS=10
   INVITE_DELIVERY_BATCH_SIZE=50
   ```

   Generate the independent encryption key locally with:

   ```bash
   .venv/bin/python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
   ```

   Keep it separate from `INVITE_TOKEN_SIGNING_SECRET` and Auth0 session
   secrets. Use the deployment secret store; do not put keys in commits,
   scheduler command arguments, tickets or logs. Both producer and worker need
   the current delivery settings. `INVITE_CANDIDATE_BASE_URL` must point to the
   HTTPS candidate route, and privacy/accommodation contact addresses must be
   working pilot addresses.

3. Install dependencies, apply canonical integration migration `20261104_0012`, and restart the API:

   ```bash
   npm run api:install
   npm run db:migrate
   ```

   Existing invitations are unchanged. Migration does not send legacy mail,
   regenerate tokens or invent delivery history.

4. Configure a deployment scheduler to run this bounded command at least once
   per minute, using the same database and secret store as the API:

   ```bash
   npm run invitations:deliver
   ```

   Multiple PostgreSQL workers may run safely: each locks the invitation before
   its delivery row, skips busy invitations, and rechecks current state. One
   batch handles at most `INVITE_DELIVERY_BATCH_SIZE` messages, each in its own
   transaction. A provider request has a bounded timeout. Monitor nonzero exit
   codes, `retrying`, `failed`, `reissue_required`, and oldest queued work; name
   an operator who can act on them. Health endpoints do not establish email
   health.

5. Add a Resend webhook at `https://YOUR-API-HOST/v1/webhooks/resend` and
   subscribe to `email.sent`, `email.delivered`, `email.delivery_delayed`,
   `email.bounced`, `email.failed`, `email.suppressed`, and `email.complained`
   where available. Inject its signing secret as
   `INVITE_WEBHOOK_SIGNING_SECRET`. Use a dedicated webhook/feed for this
   environment.

The adapter uses only `https://api.resend.com/emails`, never a client-supplied
provider origin. It supplies the verified sender, one recipient, the original
subject/text/HTML, an opaque delivery routing tag, and an idempotency header. No
questions, answers, scores or other assessment payloads are accepted by the
email boundary. Unconfigured provider/encryption/signing settings fail closed; a
provider rejects an unverified sender rather than sending a fallback email.

## API issuance and idempotency

`POST /v1/roles/{role_id}/invites` requires an authenticated, active recruiter
or administrator in that role's organization, an approved profile, a
non-archived role, and a **new UUID `request_id` for each deliberate issuance**:

```json
{
  "request_id": "a02f9f01-cd25-4bbc-8cbc-0371878dd464",
  "role_profile_id": "00000000-0000-4000-8000-000000000031",
  "email": "controlled-mailbox@YOUR-DOMAIN",
  "expires_in_hours": 24
}
```

A `201` response acknowledges durable creation/queuing, not provider acceptance
or inbox delivery. `sent_at` remains null until the worker or a signed provider
event confirms acceptance. The browser invitation form/proxy wiring remains Task
5; this task implements the authenticated API and delivery operation.

Keep the same `request_id` and input when retrying an uncertain HTTP response.
The organization-scoped request key is retained as a tombstone even after the
message is sent, cancelled or fails. Repeated identical issuance returns the
same invitation/current state without another token or job. Reusing a key with
different role, profile, recipient, expiry or replacement target returns
`409 invitation_request_conflict`. Do not solve an uncertain response by
generating a new request ID. Tenant locking also serializes competing requests
across roles.

Read safe progress at `GET /v1/roles/{role_id}/invites/{invite_id}/delivery`. It
returns an opaque job ID, status, attempt count, next attempt, retry cutoff and
safe error code. It never returns the email body, ciphertext, API key or bearer
URL. Legacy invitations without a delivery record return `404` for this
operation.

## Send failures and recovery

The provider key is always `invite/{delivery_id}`. The complete provider
payload, including sender and privacy text, is frozen at issuance, so editing
settings cannot change a retry's body. Resend deduplicates matching requests for
24 hours; this application imposes a stricter **23-hour window from issuance**,
further limited by invitation expiry. Clocks on the API, database host and
workers must be synchronized. The worker checks time again for each message, not
just once at the start of a batch.

| Situation                                                             | Behavior                                                                                                                                             | Operator action                                                                                  |
| --------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| Invitation/audit commit fails                                         | No job is committed and no provider is called.                                                                                                       | Retry the original issuance with the same request ID.                                            |
| Timeout, lost response, HTTP 408/409/429 or 5xx                       | Keep the encrypted original, mark `retrying`, and use the same provider key after exponential backoff from one minute to one hour.                   | Run the worker again; investigate sustained errors.                                              |
| Provider accepts, then worker/audit commit fails                      | Invitation and original issuance audit already exist. The same frozen message/key remains recoverable. A signed event can also reconcile acceptance. | Retry the worker, never recreate the invitation to recover this failure.                         |
| Other provider 4xx                                                    | Mark `failed`, erase the payload and revoke the old link.                                                                                            | Correct sender/key/recipient policy issues, then explicitly reissue.                             |
| Retry cutoff or invitation expiry passes                              | Mark `reissue_required`, erase the payload and revoke the link. No further provider call occurs.                                                     | Explicitly reissue if still appropriate.                                                         |
| Encryption cannot be authenticated/decrypted, or provider key changes | Mark `reissue_required`, erase the payload and revoke the old link.                                                                                  | Correct configuration; create an explicit replacement when appropriate.                          |
| Recipient server delays delivery                                      | Record `sent` with `delivery_delayed`; the provider owns downstream retries.                                                                         | Observe provider delivery status; do not send another invitation automatically.                  |
| Bounce, suppression, permanent failure or complaint                   | Record the terminal delivery result, erase pending credentials and revoke the link. Older success events cannot undo it.                             | Investigate the address/complaint; do not automatically resend or override provider suppression. |

A provider credential fingerprint is authenticated inside the encrypted
envelope. Changing a sending key therefore cannot silently retry pending work in
another provider account/deduplication scope. Drain pending work before changing
sending keys, or deliberately revoke/reissue affected invitations afterward.
There is no plaintext API key in the queue.

`POST /v1/roles/{role_id}/invites/{invite_id}/reissue` accepts a new UUID
`request_id` and optional `expires_in_hours`. It atomically revokes the old
link, erases its pending payload and creates a fresh signed link/job. Retrying
this operation with the same request ID returns the same replacement. Reissue is
allowed only while no consent/decline or assessment exists, and still requires
that the original profile be approved and its role not archived. A new profile
version requires a deliberate new issuance selecting that version. For an
incorrect recipient address, revoke the old invitation and issue to the
corrected address; reissue preserves the original recipient.

`POST /v1/roles/{role_id}/invites/{invite_id}/revoke` is idempotent and
immediately invalidates the link and cancels pending credentials. An external
send already in flight cannot be recalled. Revocation waits for that operation's
database lock, then makes any arriving email's link unavailable; it never causes
a second send.

## Queue encryption, deletion and access

Queue payloads use authenticated Fernet encryption under a dedicated random
256-bit key. Only the API producer and delivery worker should read that secret.
Limit outbox table access to these services and accountable database operators;
never expose queue columns through an ORM serializer, analytics export or admin
browser. API settings validation hides input values in configuration errors.

Decrypting an outbox payload enforces a maximum age of 23 hours. Ciphertext is
physically cleared on confirmed acceptance, permanent failure, expiry/cutoff,
revocation/reissue or candidate anonymization. Expired queued ciphertext is
cleared on the next successful worker run, so physical deletion depends on the
scheduler and backlog alerts. Keep the scheduler running even when there is no
new hiring activity. A broken worker/secret store is an operational incident,
not evidence that queued data was deleted.

To rotate encryption keys, deploy a new `INVITE_DELIVERY_ENCRYPTION_KEY` plus
the old key in `INVITE_DELIVERY_PREVIOUS_ENCRYPTION_KEY` on **all** API and
worker replicas. New messages use the new key; the worker can drain old messages
with the previous key. Remove the previous key only after old work is sent,
revoked or past its cutoff and purged. There is one previous-key slot; do not
rotate again while an older generation remains queued. Rotating the invitation
signing key is a separate operation and can invalidate outstanding links.

Backups can retain earlier ciphertext. Apply the backup retention and deletion
replay policy, keep encryption keys separate from backups, and replay
revocations and anonymization before restarting workers after a restore. The
worker's stored retry cutoff and encryption TTL prevent an old backup from
sending mail after the safe provider window. Resend necessarily processes/stores
recipient and email content, including the invitation link; its access,
retention and data-rights procedures must be included in the pilot's
provider/privacy review.

## Webhook authentication and ordering

The endpoint bounds bodies to 64 KiB and uses the maintained Svix verifier on
the **original bytes**, event ID, timestamp and signature before parsing. Stale
or invalid signatures fail closed. It persists only delivery ID, provider event
ID, event type and event time, with the delivery transition and audit in one
database transaction. Replayed event IDs have no additional effects. No
recipient, subject, bounce diagnostic body, token or entire webhook payload is
persisted.

Each send has a signed-provider echo of an opaque `delivery_id` tag. This lets a
callback reconcile acceptance even if the worker lost the send response or its
outcome commit. Callbacks without a tag can match an already stored provider
email ID. Unknown/unsubscribed events are ignored. A mismatching email ID is
rejected. Delivered/terminal states do not regress to earlier success/delay
states, and a late event never reactivates a revoked/replaced link. Webhook
signing-secret rotation is separate from sending/encryption keys; coordinate it
through the provider and deployment secret store, allowing retries/replays after
the cutover.

## Staging acceptance still required

Automated tests exercise the Resend request shape, real encryption/signatures,
timeout after acceptance, duplicate requests, audit/commit failures before and
after acceptance, frozen retries, key changes, expiry, reissue/revocation,
webhook races/replays, and actual PostgreSQL concurrency/migrations. They do not
send real email or prove a verified sender/domain or deployed scheduler.

Before closing Task 4, configure a real staging Resend account and controlled
mailbox, then record the release revision/environment and evidence that:

- One deliberate issuance produces one email, and retrying the same request
  produces no additional invitation/email.
- The worker's email opens a valid candidate consent page and reports the
  correct organization, role and expiry. The sender and privacy/accommodation
  addresses work.
- Signed sent/delivered events update progress; controlled bounce/delay and
  duplicate event tests produce the documented states without sensitive logs.
- Reissue makes the old link unavailable, revocation handles an in-flight email,
  and scheduler failure/recovery and encryption-key rotation are rehearsed.

No provider API key, verified domain, target mailbox or webhook secret was
supplied during implementation. Live mailbox and deployed-scheduler acceptance
remain pending; synthetic HTTP/signature tests do not close those operational
gates.

Local verification on November 3, 2026 passed `npm run check` with **518 tests
and zero skips**, including real PostgreSQL migration/lock tests. Configured API
application coverage remains 100%. `npm run build` and the existing
PostgreSQL-backed production HTTP smoke passed. That smoke uses seeded synthetic
invitations and does not establish real email delivery; the controlled provider
and webhook tests above cover the new delivery protocol and failure paths.

Provider contracts:
[Resend send-email API](https://resend.com/docs/api-reference/emails/send-email),
[Resend idempotency](https://resend.com/docs/dashboard/emails/idempotency-keys),
[Resend webhook verification](https://resend.com/docs/webhooks/verify-webhooks-requests),
[Svix verification](https://docs.svix.com/receiving/verifying-payloads/how),
[Fernet](https://cryptography.io/en/latest/fernet/).

## Reconciliation compatibility

Provider jobs use `provider_invitation_deliveries` and `provider_invitation_delivery_events`;
the existing local SMTP queue remains separate. The provider CLI is
`app.invitations.provider_worker`. Existing header-only `Idempotency-Key` clients
map to a stable tenant-scoped UUID; if a body `request_id` is also present it must
equal the header UUID string. Contradictory keys return 409. Both modes cannot be
enabled together. Downgrade locks both provider tables on PostgreSQL and refuses
to discard any delivery row or webhook event, including terminal tombstones.

Provider delivery/reissue browser controls are a separate coordinator-owned
followup. See [collision ledger](implementation/remote-reconciliation.md) before
considering any database previously migrated on the remote lineage.
