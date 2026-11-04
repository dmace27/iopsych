# Credential security review

Reviewed on 2026-11-04 in the isolated `iopsych-credential-review` worktree at
`b17278b`, covering credential implementation/tests `6e6b6ca` and recovery
policy/tests `42228c3`. Scope is read-only application review against the
assigned 8A contract in `report8a-durable-contract.md` and the frozen interface
in `8a-credentials.md`. The contract document still labels itself a proposal;
this review does not grant schema, deployment, or production approval. Only this
report is changed. No application, tests, dependencies, or scanner configuration
were edited.

## Result and actionable finding

No exploitable defect was reproduced in the bounded credential cipher or
token-free recovery policy. This is not a runtime delivery-security claim: queue
implementation, persistence, deletion, authorization, and transaction failure
integration evidence remain pending.

**Scanner gate failure, confirmed documentation false positive:** Gitleaks
8.24.3 reports one current-file finding and two historical findings, all under
`generic-api-key` at `docs/implementation/11a-integrated-check.md:39`.
Inspection identifies a Docker image tag containing a source revision, not a
credential. The historical commits are
`e760e4a5da368daa48d48ad7a989111537e659a0` and
`1f607df0d84d979fdb5eea0ee2a8c9dbb12ad4f6`. The documentation shows that tag
beside an image digest as packaging evidence. No matched value or raw scanner
report is reproduced here. Coordinator/scanner owner should independently
confirm the classification and apply an exact finding-scoped exception covering
the existing historical matches, then rerun both scopes. Editing the current
document alone will not clear history; do not suppress the whole rule or path.
The executed gate remains **failed**, despite the false-positive assessment.

## Contract assessment

| Area               | Assessment and boundary                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| ------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Key separation     | Constructor requires a canonical padded URL-safe base64 encoding of exactly 32 bytes and rejects reuse against supplied literal UTF-8 and decoded standard/URL-safe base64 values, including unpadded forms. Invalid forbidden-key entries fail closed. An empty tuple is permitted: integration must supply every signing/authentication key; the helper cannot discover omitted keys. Shared symmetric key access is local-only trust, not production issuer/worker permission separation. |
| Canonical encoding | Key and both 32-byte token components are decoded and re-encoded for equality, excluding alternate padding bits/alphabet forms. Token is exactly 87 ASCII bytes with one dot. Signature verification remains the invitation codec's responsibility.                                                                                                                                                                                                                                          |
| AAD                | Compact versioned JSON binds organization, invitation, delivery, expiry with microseconds, and key ID. UUID types, bounded ASCII key IDs, and UTC-offset-zero aware timestamps are checked. Separate cipher instances with identical material but different key IDs cannot open the same envelope. Persistence must retain exact expiry precision.                                                                                                                                           |
| Nonce and envelope | AES-256-GCM from cryptography uses a fresh `secrets.token_bytes(12)` nonce; envelope has a fixed 119-byte length and version marker. Every byte corruption is tested. Random nonces require bounded per-key use/retirement in integration; two differing samples are not a proof of collision impossibility.                                                                                                                                                                                 |
| Expiry             | Encrypt uses the UTC wall clock; decrypt rejects expiry at equality and later using the supplied UTC clock. The helper does not impose creation plus 15 minutes: issuer must persist `min(invite expiry, creation + 15 minutes)`, and worker must supply a trusted current clock and eligibility check.                                                                                                                                                                                      |
| Error leakage      | Tested malformed inputs, authentication failures and invalid plaintext produce the fixed `CredentialError` without retained cause/context; default cipher representation omits the key. No logging occurs here. Exception-local/argument capture by tracing remains an integration concern because Python stack locals can hold plaintext/key inputs; configure redaction/exclusion and test emitted traces before runtime acceptance.                                                       |
| Size bounds        | Key encoding is 44 characters; key ID 1–64 ASCII characters; plaintext 87 bytes; envelope 119 bytes. Oversized inputs are rejected before cryptographic work. Forbidden entries are bounded to 4096 characters each; tuple cardinality is not bounded, acceptable only for trusted startup configuration.                                                                                                                                                                                    |
| Recovery           | Terminal states delete credentials and cannot authorize retry. Only queued CLAIM increments attempts. Revocation wins; exact expiry turns sending into uncertain, queued into expired. Duplicate claims/polls do not authorize a send. Unknown acceptance or elapsed persisted grace becomes terminal uncertain; explicit reissue is external.                                                                                                                                               |

Recovery tests model committed states in memory. They do not demonstrate row
locking, actual commit/audit rollback, scheduler cleanup, SMTP behavior, or
atomic credential deletion. Runtime caller must act only on a successfully
committed claim, atomically persist state/audit/deletion, and never send merely
because the returned state is `sending`. Retain the no-retry-after-claim rule
across crashes.

## Executed verification

Installed the saved dependency manifests in this worktree with
`PYTHON_BIN=python3.12 bash scripts/install-api.sh` and `npm ci`; both completed
successfully. Python was **3.12.16**, Node **24.21.0**, npm **11.19.0**. Scanner
executables were the existing pinned local tools documented in `security-ci.md`:
Gitleaks **8.24.3** and pip-audit **2.10.0**, verified with their version
commands. No scanner/package manifests were modified.

| Command                                                                                                                                                                                                                            | Actual result                                                                                                                                                      |
| ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `PYTHONPATH="$PWD/apps/api:$PWD/packages/shared/python" .venv/bin/python -m pytest -c apps/api/pyproject.toml apps/api/tests/test_delivery_credentials.py apps/api/tests/test_invitation_recovery.py --override-ini addopts='' -q` | Exit 0; **234 passed in 0.51 seconds**. Only these two files ran; no full suite or new coverage claim.                                                             |
| `.venv/bin/pip check`                                                                                                                                                                                                              | Exit 0; no broken requirements.                                                                                                                                    |
| `.venv/bin/pip freeze --exclude-editable > /tmp/credential-review-dependencies.txt`                                                                                                                                                | Exit 0; saved installed graph, excluding only the local editable package.                                                                                          |
| `/tmp/iopsych-security-tools/audit/bin/pip-audit -r /tmp/credential-review-dependencies.txt --strict --format json > /tmp/credential-review-python-audit.json`                                                                     | Exit 0; **44 dependencies**, zero known vulnerabilities; explicit `cryptography` entry **50.0.2**, empty vulnerability list.                                       |
| `npm audit --audit-level=high --json > /tmp/credential-review-npm-audit.json`                                                                                                                                                      | Exit 0; **zero vulnerabilities at every severity**, 602 total dependencies in audit metadata.                                                                      |
| `GITLEAKS_BIN=/tmp/iopsych-security-tools/gitleaks python3.12 scripts/security-secrets.py`                                                                                                                                         | Exit 1; current-directory scope: **1 finding**, scanner exit 1; all-available-ref history: **2 findings**, scanner exit 1. Neither scope had an operational error. |

The existing wrapper uses the checked-in `.gitleaks.toml`, current-directory
`dir .` and history `git . --log-opts=--all`, 100% redaction, and deleted
private temporary raw reports. Only count summaries persist in ignored
`security-reports/secret-summary.json`. A bounded diagnostic repeat printed only
rule, path, line and commit; its temporary reports were also deleted. No new
exclusion was introduced. Available local refs are the history scope; no remote
fetch or hosted scan was performed.

An additional inline synthetic Python probe ran ten cases successfully: key-ID
AAD substitution across two cipher instances, microsecond-preserving expiry
round-trip, truncated expiry rejection, concatenated-envelope rejection,
token-newline rejection, reused key after a distinct forbidden-key entry,
one-microsecond-before-expiry acceptance, exact-expiry rejection, and revoked
queued/sending claims. Its first invocation stopped before these checks because
the synthetic signing fixture was shorter than the token codec's 32-byte
minimum; rerunning with a valid synthetic fixture passed. No repository tests
were edited. Existing tests additionally cover all 119 byte mutations, all AAD
fields, wrong material, canonical forms, malformed/oversized inputs, invalid
clocks, authenticated invalid plaintext, replay and uncertain-acceptance paths.

## Remaining acceptance evidence

Coordinator owns dependency and scanner remediation/integration. Queue owner
must prove local-only mode/key wiring, complete forbidden-key configuration,
15-minute TTL and precision preservation, trusted clocks, key loss handling,
revoke/reissue, terminal deletion and cleanup without successful sends. Targeted
runtime tests must cover concurrent claims, issuance/claim/completion audit
failure, crash after possible acceptance, revocation races, corrupt envelopes,
and absence of plaintext in storage, responses, logs and traces.

No provider calls, real email, production secrets, database operations,
listening ports, full-suite duplication, paid services, push or deployment
occurred. Dependency scanners used their public advisory services; clean results
describe this installed graph and advisory snapshot, not future vulnerability
absence. No release, full 8A, or production isolation acceptance is claimed.
