# Explicit local delivery command

This command performs one bounded drain or credential cleanup against an
operator-owned, disposable synthetic PostgreSQL database. It is not a scheduler,
production provider, or startup hook. It never migrates, seeds, creates, or resets
a database. Provision and migrate a fresh isolated database separately, with the
coordinator's current migration chain, before invoking it. Do not target an
existing development, shared, or production database.

From `apps/api`, use the project virtual environment's Python:

```sh
python -m app.invitations.local_worker_cli cleanup --once \
  --ack-database synthetic_delivery_cli --limit 25
python -m app.invitations.local_worker_cli drain --once \
  --ack-database synthetic_delivery_cli --limit 25 --smtp-port 1145
```

Configure the invoking process explicitly; `.env` files are never loaded:

| Environment variable | Required value |
| --- | --- |
| `LOCAL_DELIVERY_DATABASE_URL` | Explicit `postgresql+psycopg` URL for the owned database, numeric loopback host and explicit port, e.g. port `5605`; use independently supplied local credentials |
| `AUTH_ENVIRONMENT` | Exactly `development` |
| `INVITE_ALLOW_SYNTHETIC_DEFINITIONS` | Exactly `true` |
| `INVITE_LOCAL_QUEUE_ENABLED` | Exactly `true` |

Both operations reject any `DATABASE_URL` or `PG*` environment variable, even if
empty. Unset those variables explicitly. URLs with query parameters (including
`host`, `hostaddr`, `service`, or `options` overrides), fragments, DNS names,
missing ports, or non-PostgreSQL drivers are rejected before engine creation.
`--ack-database` must exactly match the simple database name in the dedicated URL
(ASCII letter/underscore followed by up to 62 letters, digits, or underscores).
This acknowledgement is an operator assertion of ownership and synthetic data;
the command cannot establish ownership from database contents.

All explicit endpoint ports must be 1024–65535 and must not be protected ports
`3000`, `8000`, `8001`, or `5432`. Limits must be integers from 1 through 100;
the default is 25. There is no repeat or background mode. `--once` is mandatory.

Drain additionally requires the existing `AUTH_JWT_SECRET`,
`INVITE_TOKEN_SIGNING_SECRET`, and independent `INVITE_LOCAL_QUEUE_KEY` used to
issue the queued synthetic invitations, with the matching
`INVITE_LOCAL_QUEUE_KEY_ID` if changed from its default. Supply keys through the
process environment without recording them in shell history, reports, or source
control. `INVITE_CANDIDATE_BASE_URL` must have a numeric loopback host, an explicit
nonprotected port, and no credentials, query, or fragment, for example
`http://127.0.0.1:3105/candidate/invites`. The command makes no HTTP requests.

Drain requires `--smtp-port`; `--smtp-host` defaults to `127.0.0.1` and accepts
numeric loopback only. Use an operator-owned local capture sink with relay and
forwarding disabled. The existing adapter restricts recipients to synthetic
`.test`/`.invalid` addresses. No real mail provider is configured.

Cleanup requires no signing, authentication, or encryption key, candidate URL,
or SMTP service; missing or malformed keys are ignored. It still requires all
four environment gates and database acknowledgement above. It delegates to
`cleanup_deliveries`, so stale uncertain attempts are resolved under the existing
locking/audit contract without resending mail. Drain delegates once to
`LocalDeliveryWorker.drain`, which also performs its own bounded cleanup.

Execution prints only integer counts, for example
`{"attempted": 0, "cleaned": 3}`. `attempted` counts completed worker attempts,
not confirmed recipient delivery; drain's internal cleanup is not included in
`cleaned`. Exit status 0 indicates completion, 2 indicates rejected arguments or
database/environment gates, and 1 indicates drain configuration or execution
failure. Exceptions, logs, URLs, tokens, addresses, and provider responses are
suppressed. On failure the printed counts remain zero and do not establish that
no work committed: earlier per-attempt transactions may have succeeded. Inspect
the queue through authorized local tooling before deciding on another run;
uncertain deliveries require explicit lifecycle recovery, never blind resend.

Connections have a three-second connect timeout, ten-second statement timeout,
and three-second lock timeout; SMTP uses the existing three-second per-operation
timeout. The batch is bounded by count, not a strict overall wall-clock deadline.

Verification uses fake engines/factories and fresh in-memory SQLite rejection
checks in `tests/test_local_worker_cli.py`; it does not contact existing databases
or mail servers. PostgreSQL end-to-end rehearsal is separate evidence and was
not run for this command change.
