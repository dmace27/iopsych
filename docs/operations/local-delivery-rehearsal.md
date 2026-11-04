# Local synthetic delivery rehearsal

This executable rehearses the existing local queue through authenticated API
issuance and actual Mailpit SMTP capture. It is a disposable engineering check,
not a production scheduler, provider selection, hosted acceptance or real-mail
authorization. No API or web listener is started: FastAPI's in-process
TestClient executes the actual POST and candidate routes, authentication and
transactions.

## Run

Wait for the worktree setup installer to finish successfully. Use the installed
Python environment with API, shared contracts and test dependencies. Docker
Desktop's `desktop-linux` context must point to an absolute local Unix socket;
both `postgres:16-bookworm` and `axllent/mailpit:v1.27.10` must already be
cached. The harness never installs dependencies or pulls/builds images.

```sh
.venv/bin/python -m pytest scripts/verification/test_local_delivery_rehearsal.py -q -o addopts=''
.venv/bin/python scripts/verification/local_delivery_rehearsal.py --project iopsych-delivery-rehearsal
```

Explicit project acknowledgement is mandatory. Remove ambient database, PG,
Docker target, test, authentication, invitation and provider configuration from
the invoking environment yourself; the harness refuses it, including empty
values. Root `.env` and `apps/api/.env` must be absent. Never remove a real
configuration file just to run this check: use a clean isolated worktree.

The fixed allocations are PostgreSQL `127.0.0.1:5599`, database
`iopsych_delivery_rehearsal`, SMTP `127.0.0.1:1140` and Mailpit HTTP
`127.0.0.1:8140`. Busy ports cause failure; no process is stopped to claim them.
Protected 3000/8001/8000/5432 and existing databases are untouched.

## Isolation and credential handling

Each run creates randomly named, ownership-labelled containers and an owned
bridge with IP masquerading disabled. Only loopback ports are published. Mailpit
has no relay/forwarding configuration or provider credentials. The bridge is not
a general host firewall or a claim of isolation from hostile local operators.
PostgreSQL data and Mailpit messages live on bounded tmpfs mounts; Mailpit's
root filesystem is read-only and container logging is disabled. PostgreSQL is
migrated to repository head and seeded only after creation of the fresh owned
container.

Ephemeral signing/encryption keys are generated in process. The candidate bearer
URL is read from the disposable Mailpit capture, resolved through the candidate
API, and never printed or written to an artifact. Its only intentional plaintext
storage is the in-memory message capture required to prove delivery. Python
request logging and exception tracebacks are suppressed, and audit metadata is
checked for token absence. The script prints only fixed PASS/failure messages.

Cleanup verifies the exact owner label before removing each resource, including
volumes; it never prunes, drops an existing database or performs a shared reset.
Cleanup also runs after ordinary failures and Ctrl-C. A process kill or host
crash can leave labelled resources: inspect only this rehearsal's ownership
labels and remove the exact owned containers/network manually, never use a
global prune.

## Evidence exercised

- Signed synthetic recruiter JWT and real POST issuance, with duplicate key
  returning the same invitation and only one queue row; SMTP is empty before
  drain.
- Bounded existing `LocalDeliveryWorker.drain`, exactly one real captured
  message, consent URL resolution to the expected invitation and notice, and
  empty repeat drain.
- Terminal sent state, one attempt, erased ciphertext/key ID, required issuance,
  queued, sending and sent audit records, and minimal delivery audit metadata.
- A second actual SMTP acceptance followed by an injected completion-commit
  failure using a scoped SQLAlchemy listener. The listener is removed in
  `finally`. Existing cleanup runs at a synthetic three-minute recovery time,
  producing uncertain state, erased credentials and an uncertainty audit. Repeat
  drain sends nothing and the same issuance key receives HTTP409 rather than
  automatic reissue.

The recovery fault is an intentional database transaction failure after SMTP
acceptance, not a simulated SMTP server or proof of every network failure mode.
This check does not consent on anyone's behalf, submit an assessment, test a
real provider or prove browser rendering, concurrency, production scheduling or
hosting.

## Verification record

On 2026-11-04, after the coordinator confirmed the worktree installer completed,
the harness passed the full live sequence above against fresh PostgreSQL and
Mailpit containers against application revision
`37da365ed27659d4c08df74bab325353432f3164`. Both PASS lines and
ownership-checked cleanup completed with exit status zero. Thirty hermetic
harness guard tests passed; Ruff check and format verification passed. A
pre-existing Starlette/TestClient deprecation warning appeared; no dependency
changes were made.

An initial prerequisite check rejected an uncached `latest` Mailpit tag; the
final harness pins the cached `v1.27.10`. An initial internal bridge did not
publish ports on this Docker Desktop configuration; that run was interrupted
before API issuance and ownership cleanup succeeded. The final private bridge
with IP masquerading disabled successfully published the loopback-only ports.
Local Docker calls briefly stalled during that attempt and subsequently
recovered. No queue/runtime files, dependency manifests, existing DBs or
protected listeners were modified. Independent queue review and broader
hosted/provider gates remain outside this rehearsal's evidence.
