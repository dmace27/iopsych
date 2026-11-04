# Existing notice snapshot engineering contract

This additive milestone implements only pure helpers and synthetic tests. It
does not approve versioned terms, change policy, alter the existing 90-day
default, or implement the broader [10A proposal](10a-contract.md). The existing
assignment snapshot remains separate and untouched. Integration below reflects
the coordinator's additive-v1 direction, superseding this worker's initial v2
proposal; integration files are not owned by this milestone.

## Canonical payload

`app/privacy/notice_snapshot.py` accepts exactly:

```json
{
  "schema_version": 1,
  "consent_notice": {
    "version": "synthetic-v1",
    "purpose": "Existing rendered purpose",
    "data_use": "Existing rendered data use",
    "retention": "Existing rendered retention statement",
    "accommodation_contact_email": "access@example.invalid",
    "privacy_contact_email": "privacy@example.invalid",
    "decline_without_penalty": true
  },
  "retention_days": 90
}
```

The example is synthetic, not approved copy. Callers supply the complete existing
rendered `ConsentNotice` and the same retention setting used to render it, from
one settings instance. Helpers do not invent copy or infer days from prose.
Exact keys and types are required, with no coercion, trimming, Unicode
normalization, implicit defaults, or ignored extensions. Text must be nonblank
valid UTF-8; version has the existing 80-character storage limit. Integer days
have the existing settings range 1–3650; booleans are not integers here.

Canonicalization is Python JSON with `sort_keys=True`, `separators=(",", ":")`,
`ensure_ascii=False`, `allow_nan=False`, encoded UTF-8. SHA-256 is lowercase
64-character hexadecimal over the complete payload, excluding the digest
itself and mutable timestamps/provenance. Every displayed field and retention
days participate. Helpers return detached copies. `InvalidNoticeSnapshotError`
means invalid/unknown stored content or integrity failure;
`NoticeReviewRequiredError` means missing, malformed, or unequal presented
digest. Integrity is checked before client equality. Neither hashing nor a
matching digest proves that a human read the notice.

## Proposed migration and persistence

Coordinator will allocate migration 0011 after the pure milestone. Add nullable
`assessment_invites.notice_snapshot_json`, `notice_sha256`,
`notice_snapshot_origin` (`issued`, `first_presented`, or `legacy_decision`), and
`notice_snapshotted_at`. Enforce all-four-null or all-four-populated and digest
shape constraints. Freeze populated snapshot fields with ORM and database
guards, allowing one atomic NULL-to-snapshot transition only for an undecided
legacy invite under its row lock. No assignment edits are required.

Add nullable `candidate_consents.presented_notice_sha256` and nullable
`notice_evidence` (`digest_recorded` or `legacy_unverified`). Existing consent
rows retain both NULL, interpreted as `legacy_unknown`; a new omitted-digest
decision explicitly stores `legacy_unverified`. Digest evidence requires a
non-null matching digest, persisted in the same transaction as the terminal
decision and audit. Do not backfill existing content, proof, days, or deadlines.
Do not change existing consent decisions or reconstruct erased data.

New issuance freezes existing copy/days before delivery. An undecided legacy
invite may freeze current copy on first GET, marked `first_presented`, never
`issued` and never historical evidence. An old POST arriving first may freeze
current settings solely for future retention consistency but must mark the
decision `legacy_unverified`; its origin must be explicitly `legacy_decision`.
Do not label that event first presentation. Preexisting decided invitations
retain NULL snapshot and digest; any current copy returned is not historic copy.

## Same-v1 GET / POST / UI handshake

Keep `/v1/candidate/invites/{token}` and its `/consent` POST. GET adds optional
nullable `notice_sha256` and optional `notice_history`. Recommended history enum:

| Value | Meaning |
| --- | --- |
| `not_recorded` | No terminal decision exists. |
| `digest_recorded` | Decision included the digest matching the stored snapshot. |
| `legacy_unverified` | New decision explicitly accepted without a digest. |
| `legacy_unknown` | Existing decision has no historical snapshot evidence. |

GET takes the invite lock when initializing legacy content, validates stored
integrity, and renders only the stored snapshot when present. For preexisting
decided legacy invites, digest remains NULL and history is `legacy_unknown`;
current notice copy must not be described as the copy previously accepted.
All candidate responses carrying this metadata use the same semantics.

POST adds optional nullable `presented_notice_sha256`. Under the invite row
lock, resolve expiry/revocation and the terminal decision first: opposite
decisions remain conflicts. For any supplied non-null digest, compare it with
the stored snapshot and digest before any decision/status/audit mutation;
mismatch returns 409 `notice_review_required`, with no writes. Invalid stored
content fails closed as `notice_snapshot_unavailable`, not a fabricated snapshot.
Digest-less legacy requests remain accepted and explicitly unverified, including
explicit null for compatibility; the new UI must never use that fallback.
Same-decision omitted-digest retries remain idempotent and never upgrade old
evidence. Supplied-digest retries cannot rewrite existing decision evidence.
The pure presentation checker always rejects missing digests; the service must
deliberately select the legacy compatibility branch instead of bypassing it
accidentally. No helper provides database serialization by itself.

The UI renders the returned notice, retains its accompanying digest in the same
view state, and echoes it on both consent and decline. On 409 it fetches the
current notice, clears any previous acknowledgement, displays review-required
state, and requires another explicit decision; no automatic POST retry. It
does not claim historic display for unknown or unverified evidence. Update the
strict TypeScript response/request schemas together: optional server fields
alone do not preserve old clients that reject extra fields. Rollout therefore
requires permissive/new clients first or response capability negotiation before
advertising extra fields to old strict clients.

Submission uses frozen days for snapshots with validated integrity and keeps
the existing submitted-at anchor. Stored deadlines never change. Existing
legacy rows without snapshots retain current legacy behavior and uncertainty;
this slice does not resolve NULL deadline policy or introduce new clocks.

## Verification and remaining acceptance

Focused command from `apps/api`:

```sh
../../.venv/bin/python -m pytest tests/test_notice_snapshot.py --noconftest -o addopts='' --cov=app.privacy.notice_snapshot --cov-branch --cov-report=term-missing --cov-fail-under=100
../../.venv/bin/ruff check app/privacy/notice_snapshot.py tests/test_notice_snapshot.py
../../.venv/bin/ruff format --check app/privacy/notice_snapshot.py tests/test_notice_snapshot.py
MYPYPATH=../../packages/shared/python ../../.venv/bin/mypy app/privacy/notice_snapshot.py
```

Executed results: **46 passed**, **100% statement and branch coverage** for the
new module; Ruff lint/format and scoped mypy passed. Mypy requires the explicit
shared-package path above; the initial invocation without it reported missing
shared imports. `git diff --check` passed. These are pure-module results only.

Pure tests cover exact serialization, detached copies, every displayed field,
retention boundaries, coercion rejection, malformed Unicode, unknown history,
stored corruption, and stale/missing presentation. No database fixture, service,
network, real mail, secret, reserved port, or policy source is used.

Integration acceptance remains: populated SQLite/PostgreSQL migration guards;
old/new strict client rollout; simultaneous GET/POST and opposing decisions;
stale digest with zero writes; explicit legacy evidence and unknown history;
unchanged retry decisions; configuration changes after issuance; preserved
stored deadlines; and manual review UI behavior. Pure tests are not concurrency
evidence. Full 10A remains partial for legacy presentation proof and policy.
