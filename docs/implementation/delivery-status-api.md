# Invitation delivery visibility API

Implemented on the isolated delivery-status API child of `e439208` for phase 8A/8B
of `final-implementation-plan.md`. No applicable API AGENTS file was present;
the web-only AGENTS file is outside this change. Terminal metadata confirmed
inherited GPT-6-Astra medium Fast mode; no mode changes were made.

## Contract and compatibility

Every successful create, revoke, and list-item response includes the additive
`delivery_state` field. Its values are `null`, `queued`, `sending`, `sent`,
`uncertain`, `cancelled`, or `expired`. Existing invitation `status` is unchanged.
An absent or tenant-inconsistent queue row yields `null`, including legacy
synchronous invitations with `status: "active"` and a populated `sent_at`.
Null means delivery state is unknown; it does not establish delivery success.

Synthetic complete list fixture (the same item shape is returned by create/revoke):

```json
{
  "items": [
    {
      "id": "00000000-0000-0000-0000-000000000001",
      "role_profile_id": "00000000-0000-4000-8000-000000000031",
      "email": "synthetic@example.invalid",
      "expires_at": "2026-11-05T12:00:00Z",
      "status": "pending_delivery",
      "delivery_state": "uncertain",
      "sent_at": null,
      "revoked_at": null,
      "created_at": "2026-11-04T12:00:00Z"
    }
  ],
  "next_cursor": null
}
```

For compatibility fixtures, substitute each of the other five enum strings or
JSON null for `delivery_state`. The frontend schema must accept an optional,
nullable enum for rolling compatibility with older API responses; this API
always emits the field. Strict frontend schemas must be updated before combined
acceptance. No database migration or new configuration is required.

`uncertain`, `expired`, and `cancelled` are terminal delivery states and must not
be labeled as active pending work. The existing explicit revoke followed by
confirmed new issuance remains the recovery path; this change introduces no
retry, reissue, or queue mutation. `sent` reports persisted delivery acceptance,
not proof of mailbox receipt.

## Implementation and isolation

The shared response helper projects only queue invitation ID and state. It joins
through invitation, profile, and role and requires both the queue organization
and role organization to match the authenticated organization. Discovery passes
only the returned page IDs (at most 100), excluding the pagination lookahead;
create/revoke pass one ID. Empty pages issue no queue query. Nonempty pages use
one batch query, avoiding N+1 queries. Credential ciphertext, key identifiers,
digests, and additional recipient details are neither selected nor exposed.

Only schemas, discovery, router, the related discovery exact-shape assertion,
new visibility tests, and this report changed. Queue, service, worker, models,
migrations, dependencies, and reviewer-owned queue tests remain untouched.

## Validation and handoff

Targeted command:

```sh
.venv/bin/python -m pytest apps/api/tests/test_invitation_delivery_visibility.py apps/api/tests/test_invitation_discovery.py apps/api/tests/test_invitations.py --no-cov -q
```

Result: 35 passed. Coverage includes all six states, unknown legacy delivery,
unchanged invitation status, exact safe response shape, foreign queue corruption
in both directions, tenant denial, one projection query at page sizes 1 and 100,
and consistent create/revoke fields. The queued-create response test stubs only
the PostgreSQL-only issuance service and hydrates a persisted synthetic queue row;
revocation runs the actual service. This is visibility evidence, not a new
PostgreSQL queue lifecycle or SMTP acceptance run.

Ruff checks and focused mypy checks cover the changed Python implementation and
new tests. Mypy requires `MYPYPATH=packages/shared/python:apps/api` when checking
these files alone. The first test attempt found a fixture attribute typo, fixed
before the passing run; the first mypy attempt found missing shared-package path
configuration and a row-conversion typing issue, both corrected.

No full suite, real mail, existing database reset, pushes, deployment, protected
port changes, or integration merges were performed. Coordinator owns integration
and combined API/UI acceptance; the parallel frontend schema update is the
remaining integration dependency. No API implementation blockers remain.
