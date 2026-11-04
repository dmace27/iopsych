# Invitation integration merge review

Reviewed UI `eeea1da` (source `237d9f2`), queue `a60b115`, proxy
`aa23c1e` (integration `e439208`), packaging `e465da4`/`5b68e5b`, and
account hardening `85e7286` (integration `1d269c4`). This child started at
`eeea1da` and was fast-forwarded with coordinator authorization to exact
baseline `1d269c49649003715380423bd6bb436d47a2b615`; app files are read-only.
Read the accelerated schedule and progress ledger and the web
AGENTS guidance; no ancestor or docs AGENTS was present. Live terminal screen
displayed `GPT-6-Astra medium fast`; no setting was toggled.

## Findings requiring UI follow-up

1. **Queue recovery loses its required action.**
   `apps/web/lib/invitation-issuance-client.ts:33` replaces every API problem
   code with `invitation_issuance_failed`. The form's `showError` maps every
   409 to profile/role/expiry advice, and offers confirmation again with the
   same key. `queue.py:113` rejects expired/cancelled/uncertain delivery and
   revoked/expired invitations with `invitation_reissue_required`; repeated
   confirmation cannot resolve this. `Start new invitation` is shown only
   after success. Users can incidentally reset the key by editing a field,
   but are never told to revoke an unresolved invitation before reissuing.
   Preserve an allowlisted problem code without exposing raw detail, show the
   specific revoke/reissue action, and require explicit confirmation before
   replacing the key. Keep the same key for transport/ambiguous-response retry.
   Reproduce with POST 409 `invitation_reissue_required`, then confirm twice;
   assert specific guidance and an explicit, usable recovery path.

2. **Refresh can strand the shared issuance lock.**
   `invitation-workspace.tsx:114` clears readiness/history on refresh but
   retains title and form, and does not mark refresh busy. The mounted form
   receives only `disabled={busy}`. Start a deferred history refresh, then
   confirm a preview while it is pending; let refreshed role become archived
   before the deferred issuance settles. The form unmounts, setting its
   `alive` ref false, so its `finally` at `invitation-issue-form.tsx:114`
   skips `onBusyChange(false)`. The still-mounted workspace retains
   `issuing=true` and disables history actions indefinitely. Mark history
   refresh pending and exclude issuance throughout it, preserve the existing
   request key during ordinary refresh, and ensure parent busy ownership
   survives conditional form removal. Add deferred success and rejection
   tests, including archive and permission changes during refresh.

Both findings were escalated immediately as source-derived reproductions;
they were not independently reproduced in a running browser in this review.
Do not interpret existing passing tests as coverage of these sequences.

## Wire and behavior checks

| Boundary | Required behavior and review result |
| --- | --- |
| Browser request | POST `/api/internal/roles/{roleId}/invites`; strict `{role_profile_id,email,expires_in_hours?}`; expiry integer 1–720; JSON Accept/Content-Type; no-store; random UUID `Idempotency-Key`. |
| Proxy | `aa23c1e` allows exact UUID-role issuance only, maps to `/v1/roles/{role_id}/invites`, keeps origin and cookie-derived bearer checks, forwards present visible-ASCII keys of length 16–128 unchanged, and leaves missing-key/body policy to API. GET/revoke do not forward the key. |
| Response | API returns 201 for both new issuance and replay. Client accepts only 201 and strict token-free invitation representation; invalid success becomes unknown outcome. Proxy retains status, content type, Retry-After, no-store; 204 is intentionally not accepted as issuance success. |
| Queue retry | Enabled local PostgreSQL queue requires a key, hashes normalized request plus role, scopes keys by tenant, returns same invitation for eligible replay, and conflicts on different payload. Default synchronous path does not implement key deduplication. Never claim exactly-once delivery for this UI. |
| Truthful status | UI says recorded/stored status and explicitly does not confirm receipt. Pending does not mean sent; active does not establish receipt. History has no delivery-job recovery detail. |
| Approval/archive | Form filters approved profiles; archived role hides issuance. Server checks tenant role/profile, current approval, archive and expiry policy for new issuance. Eligible queue replay precedes current archive/approval checks because it returns an existing invitation rather than creating one. |
| Permissions | API requires admin/recruiter. Initial manager lookup stops workspace loading; 401/403/404 issuance removes its form, 401 offers sign-in. A form-local permission error does not immediately clear already-loaded history; later history requests remain server-authorized. |
| Role navigation | Workspace keys its entire child by role ID, so actual route changes reset draft/key/result and isolate old callbacks. The form's bare `alive` guard is not a general role-change generation guard; retain the keyed wrapper if refactoring. Existing tests cover late list/revoke work and standalone form unmount, but not pending issuance across a workspace role switch. |
| Focus | Existing revoke/final-page focus destinations and user-moved-focus protection remain. New issuance has no explicit focus destination when permission denial removes confirmation; success leaves confirmation disabled. Add keyboard browser checks for preview, success, denial, new request and role switch; do not infer these from old list focus tests. |

## Merge/conflict guidance

- Integrate proxy with UI before calling issuance functional: `eeea1da` alone
  rejects POST with local 404 and discards idempotency headers. Coordinator
  reports proxy accepted as `e439208`; do not cherry-pick its source again.
- Retain both account GET/PATCH entries and invitation POST in the shared
  proxy allowlist. Preserve candidate/privacy/report routes, same-origin
  validation, server-only bearer construction, scoped key forwarding and
  no-store headers. Never resolve a future conflict by replacing the whole
  allowlist from an older child.
- Packaging adds only canonical report fixtures to the Docker build stage.
  Keep `COPY apps/api/tests/fixtures/report_trace ...` before `npm run build`;
  `5b68e5b` removes only new explanatory comments. There is no file overlap
  with issuance UI/proxy. A fresh image build is still the package owner's
  gate; this review does not duplicate it or exclude tests from typechecking.
- Account hardening `85e7286` touches migration 0010, its PostgreSQL tests and
  its report only. Preserve 0010's parent 0009 and queue 0009 unchanged.
  Its downgrade guard locks users and refuses disabled-account loss; queue
  credential rollback has its own guard. Do not bypass either to make a
  rollback test pass. Account tests require exact local 5594/iopsych_access
  with no URL query overrides; that allocation belongs to their owner.
- No textual overlap exists among the reviewed feature changes. Behavioral
  coexistence still needs the combined revision's targeted checks. Security
  and queue concurrency review remain with their assigned owners.

## Targeted verification and handoff

After the saved installer finishes, from `apps/web` run only these selected
tests, without full-suite coverage:

```sh
../../node_modules/.bin/vitest run --coverage.enabled=false lib/invitation-issuance-client.test.ts 'app/roles/[roleId]/invites/invitation-issue-form.test.tsx' 'app/roles/[roleId]/invites/invitation-issuance-integration.test.tsx' 'app/roles/[roleId]/invites/invitation-workspace.test.tsx' 'app/api/internal/[...path]/issuance-route.test.ts' 'app/api/internal/[...path]/invitation-route.test.ts'
```

The proxy test exists only after its integration. Add the two reproductions
above to the UI owner's tests, plus pending issuance across role-ID change,
late 401/403/404, 409 unapproved/archive, and keyboard focus after removal.
Existing tests mock the issuance client; they do not prove browser-to-proxy-to-API
composition. Browser owner should exercise synthetic issuance/replay and
failure paths on their allocated ports, using controlled local delivery only.

For the backend owner, from `apps/api`:

```sh
../../.venv/bin/python -m pytest --no-cov -q tests/test_invitations.py -k internal_invite_rules_enforce_approval_tenant_role_and_expiry_policy
../../.venv/bin/python -m pytest --no-cov -q tests/test_delivery_queue.py -k 'queue_commits_before_send or conflict_and_cross_tenant_replay or timeout_requires_revoke_reissue or api_pending_response_compatible_and_replayed'
```

The queue selection requires its owner's explicit isolated PostgreSQL fixture;
skips are not queue evidence. Do not borrow protected/default ports or reset
existing databases. Account owner's 40 passed/zero-skipped report at `85e7286`
is external evidence, not an independent rerun here.

Saved installer completion was directly verified in its terminal as
`__ORCA_SETUP_COMPLETE__:f9f91541-ecb7-4fef-b815-05df4aca6830:0`.
Coordinator reports **446 web tests passed with coverage gates at `e439208`**;
this is coordinator evidence, not an independent run. Per its follow-up,
duplicate focused happy-path and full-suite runs were intentionally omitted.
The commands above are precise handoff commands, not claimed executions.
No application test was independently run and neither new failure sequence was
dynamically reproduced by this document-only worker. Report whitespace was
checked with `git diff --cached --check` before committing only this document.
No container build, database, server, real mail, secret access, push or deployment
was performed. Remaining gates are the two UI findings, focused merged checks,
actual keyboard/browser integration, packaging rebuild and separately owned
queue/account verification; provider, hosted/manual and pilot approvals remain
outside this bounded merge review.
