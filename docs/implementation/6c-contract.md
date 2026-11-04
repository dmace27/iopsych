# 6C bounded compatibility contract

Contract agreed with coordinator on 2026-11-04, base `4638236`.
This is decision-independent engineering, not package acceptance or content approval.
6B decisions and actual I-O review remain pending. Scientific v1 behavior, including
inverse structure matching, is unchanged. No provider is selected.

## Candidate API and UI handoff

Existing landing and consent response shapes and submit payload remain unchanged
(the frontend validates those responses strictly). No new fields are added to
those endpoints or to internal invite responses in this slice.

New `GET /v1/candidate/invites/{token}/definition` returns HTTP 200:

```json
{
  "assignment": {
    "assessment_definition_id": "work-preferences-pilot",
    "assessment_definition_version": "1.0.0",
    "scoring_version": "1.0.0",
    "matching_algorithm_version": "1.0.0",
    "definition_sha256": "021233ca4dab9c86b87aeabca88f503bf7c70fd0b0d324c64e788b620aeb6e3c"
  },
  "definition": "the complete existing AssessmentDefinition object, not this placeholder"
}
```

Use the actual definition ID in the returned payload. The definition includes its
existing ID/version/status/title, six blocks and scoring configuration. It contains
no candidate responses, scores or classifications. The endpoint requires a valid,
unexpired, non-revoked, delivered invite and affirmative consent; rate limiting,
no-store headers and token-safe access auditing apply. Before consent or after
decline it returns 409 `candidate_consent_required`; expired/revoked and invalid
credentials preserve existing 410/404 handling. Unknown/malformed/missing assignment
returns 409 `unsupported_assessment_version`, never the current default.

Frontend handoff: fetch after consent, validate the new envelope, render its
`definition`, and persist/restore drafts only for its exact ID/version (and hash
in new draft envelopes). Submit the existing AssessmentResponseSet shape. Do not
fall back to the imported current definition when fetch fails. Existing v1 drafts
retain identical item/block/definition IDs and remain compatible. Browser behavior
and migration of local draft storage are separate work, not verified here.

## Snapshot, eligibility and historical dispatch

`assessment_invites.assignment_json` is an additive nullable JSON column storing
`{contract_version: 1, definition: <full object>, definition_sha256: <sha256>,
matching_algorithm_version: "1.0.0"}`. Issuance writes the snapshot before delivery.
Submission scores this snapshot and copies it into existing assessment storage.
The hash is UTF-8 SHA-256 of JSON serialized with sorted keys, compact separators,
and unescaped Unicode. Readers verify it; it is an integrity check, not a signature.

`app/assignments/definitions/legacy-v1.json` is a frozen, checksum-verified copy of
the original draft. Explicit scoring, matching and report-reader maps retain v1.
Unsupported IDs/versions/scoring configurations/algorithms fail closed. New versions
must add retained readers and matching API/frontend contracts, never replace v1.
Stored report reads select by the stored algorithm, validate the stored result and
return its original interpretation without recomputing scores or matching.

New invitations default to reviewed-only eligibility. There is no reviewed entry;
`INVITE_ALLOW_SYNTHETIC_DEFINITIONS=true` is the explicit development/test opt-in
for the existing draft, not reviewer approval. New retired assignments are denied.
Previously pinned assignments remain readable/scorable regardless of later new-
assignment policy or retirement. No runtime flag is needed to read historical
assignments. This does not authorize their use in a real pilot.

SQLite and PostgreSQL triggers reject any change to the complete assignment
snapshot, including SQL/bulk writes and NULL-to-value updates. Other invitation
lifecycle fields remain editable; privacy deletion remains possible. Database
owners can bypass/drop triggers, so these guards do not protect against privileged
schema tampering. There is no assignment mutation API or automatic repair fallback.

## Migration and preserved history

Exclusive migration slot `20261104_0008`, parent `20260929_0007`. Its own frozen,
checksum-verified `alembic/definitions/legacy-v1.json` is independent of the current
runtime definition. Unsubmitted legacy invites receive exactly this v1 snapshot.
Submitted invites receive their original definition only if exactly recognized as
the frozen v1 content. Unknown/malformed submitted history stays NULL/unsupported;
no guesses or current-default fallback. Anonymized submissions remain unassigned,
and no deleted answers or scores are restored. Existing assessment and report JSON
is never modified or recomputed. Downgrade removes only the additive column/guard.

Legacy pending, consented, submitted, retired/expired, malformed, unknown and
anonymized cases must be checked through populated upgrades. Focused tests cover
historical v1 response compatibility and report interpretation, new-policy gates,
snapshot tampering, consent/token gates and SQLite/PostgreSQL mutation guards.
