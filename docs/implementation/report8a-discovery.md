# 8A bounded invitation discovery slice

Implemented additive `GET /v1/roles/{role_id}/invites?limit=25&cursor=...` returning `{items: InvitationResponse[], next_cursor: string | null}`. Existing POST, revoke and candidate contracts are unchanged. No migrations, dependencies, provider configuration, service changes or startup changes.

## UI contract

- Authenticated ADMIN and RECRUITER only; hiring manager receives 403, unauthenticated receives 401.
- `limit` defaults to 25; integers 1–100 accepted. Invalid limits produce the existing 422 validation problem.
- Omit `cursor` for the first page; pass the exact returned `next_cursor` for subsequent pages. Null means exhausted; empty history is exactly `{"items":[],"next_cursor":null}`. Changing page size is allowed.
- Order is `created_at DESC, id DESC`, across all profile versions for the role. Archived role history remains readable. Issuance gates remain unchanged.
- Each item is precisely the existing InvitationResponse: id, role_profile_id, email, expires_at, status, sent_at, revoked_at, created_at. Nullable sent_at/revoked_at stay null. Status is the stored enum: pending_delivery, active, consented, declined, revoked, expired. This read does not synthesize expiry or submission statuses.
- Foreign and nonexistent role IDs return the same 404 problem. Malformed, noncanonical, fabricated-anchor and mismatched tenant/role cursors return generic 422 `invalid_invitation_cursor`; no supplied cursor or internal decoding detail is reflected.
- All responses inherit `Cache-Control: no-store`. Existing process-local invitation limiter uses `invite-list:{user_id}` and configured internal budget; 429 includes Retry-After. Existing audit middleware emits assessment_invite.listed, entity_type role, role ID, and allowlisted method/status/outcome metadata; audit write failure withholds results.

## Cursor and consistency

The current cursor is a canonical 102-character base64url reference containing a version byte, tenant UUID, role UUID, invitation UUID, and UTC creation timestamp. It contains no email, token hash, raw bearer credential or invitation link. It is intentionally unsigned and not an authorization credential: every request reauthenticates, scopes every database query by role and tenant, and checks the complete reference against the stored anchor. Constructing a reference to another valid anchor within the same authorized role is equivalent to selecting that starting position and grants no extra access. No key/provider/outbox choice is needed, including when invitation signing configuration is absent.

Keyset pagination avoids duplicates or offsets shifting when newer invitations arrive. This is not a snapshot: new rows older than the boundary can appear, and status changes are reflected. Deleting the cursor anchor invalidates that cursor; UI should offer restarting the list on invalid_invitation_cursor. The result query fetches at most limit+1 rows (101), plus bounded role and anchor lookups. No new indexes or performance claims at production scale; PostgreSQL query-plan assessment remains separate.

## Exact synthetic wire fixtures

These were generated through the actual ASGI endpoint against a disposable in-memory SQLite database with two synthetic invitations and no signing key/delivery adapter. No bearer credentials are included.

### First page: GET /v1/roles/00000000-0000-4000-8000-000000000021/invites?limit=1

```json
{
  "items": [
    {
      "id": "00000000-0000-0000-0000-000000000002",
      "role_profile_id": "00000000-0000-4000-8000-000000000031",
      "email": "synthetic-2@example.invalid",
      "expires_at": "2026-11-05T12:00:00Z",
      "status": "consented",
      "sent_at": null,
      "revoked_at": null,
      "created_at": "2026-11-04T12:00:00Z"
    }
  ],
  "next_cursor": "AQAAAAAAAEAAgAAAAAAAAAEAAAAAAABAAIAAAAAAAAAhAAAAAAAAAAAAAAAAAAAAAjIwMjYtMTEtMDRUMTI6MDA6MDAuMDAwMDAwWg"
}
```

### Last page: same path with limit=1 and previous next_cursor

```json
{
  "items": [
    {
      "id": "00000000-0000-0000-0000-000000000001",
      "role_profile_id": "00000000-0000-4000-8000-000000000031",
      "email": "synthetic-1@example.invalid",
      "expires_at": "2026-11-05T12:00:00Z",
      "status": "active",
      "sent_at": null,
      "revoked_at": null,
      "created_at": "2026-11-04T12:00:00Z"
    }
  ],
  "next_cursor": null
}
```

### Invalid cursor: HTTP 422

```json
{
  "type": "about:blank",
  "title": "Validation failed",
  "status": 422,
  "detail": "The invitation cursor is invalid.",
  "instance": "/v1/roles/00000000-0000-4000-8000-000000000021/invites",
  "code": "invalid_invitation_cursor"
}
```

## Verification and remaining scope

- `.venv/bin/pytest -c apps/api/pyproject.toml apps/api/tests/test_invitation_discovery.py apps/api/tests/test_invitations.py --no-cov -q --tb=short`: **29 passed**, no skips. Includes 17 new discovery cases plus existing invitation regression tests, synthetic isolated SQLite only; no ports or existing database touched.
- `.venv/bin/ruff check apps/api/app/invitations/{discovery,router,schemas}.py apps/api/tests/test_invitation_discovery.py`: passed; Ruff format applied.
- `MYPYPATH=packages/shared/python:apps/api .venv/bin/mypy --config-file apps/api/pyproject.toml apps/api/app/invitations/discovery.py apps/api/app/invitations/router.py apps/api/app/invitations/schemas.py apps/api/tests/test_invitation_discovery.py`: passed, four files. Initial invocation without the shared-contract import path failed import resolution; corrected invocation passes.
- Tests cover defaults/max/invalid limits; tied timestamps and timestamp precedence; concurrent newer insert; all profile versions; archived history; empty/exhausted pages; malformed/oversized/altered cursors; tenant/role binding; authorization; safe response/audit shape; throttling; missing provider/key; and audit failure.

This completes only the assigned discovery slice. Full 8A acceptance, issuance idempotency, durable outbox/recovery, real provider delivery/webhooks, staging and production-scale/PostgreSQL verification remain outstanding. Next eligible work is UI integration using this additive contract; this report does not assert delivery-lifecycle acceptance.
