# Synthetic rehearsal and release evidence

Status: **not executed**. This document prepares 12C; it does not close original
5C. Rehearsal lead and all approval roles: owner-unassigned. Full execution
waits on 10C, 11A–C, completed feature journeys, 12A/12B and authorized
environment access.

## Execution protocol

1. Record release SHA, environment, UTC window, operators, browser/device
   versions, schema/assets versions and exact reviewed commands. Use 11A's
   `deploy/README.md` and `docs/implementation/11a-report.md` once reviewed; no
   deployment commands are assumed here.
2. Confirm synthetic-only fixtures, two isolated tenants, distinct
   recruiter/manager/admin identities, deterministic extraction and controlled
   loopback mail with no external delivery. Confirm allocated web/API/database
   targets; this worker's reservation is `3108`/`8108`/`5548`, database
   `iopsych_runbooks`. Do not alter shared ports, databases or a concurrently
   running setup.
3. Use 12A's reviewed runner once available. Current command inventory is in
   [deployment](deployment-rollback.md); API operations are in
   [rights](support-rights-training.md). Capture actual command, exit code,
   sanitized evidence path and observed result per row below. A manual action
   needs its precise steps and expected/observed state too.
4. Use separate synthetic invitations for decline, complete, partial skip,
   expiry, revocation and storage failure. Use an unapproved role and another
   tenant for negative checks. Keep raw tokens only in the controlled
   mailbox/browser context, never screenshots/logs/reports. Do not count
   directly seeded approval or injected JWTs as evidence of provider login or
   manager handoff.
5. Run failure, retention, backup/replay and rollback stages only through their
   reviewed procedures in isolation. Stop at any unmet dependency rather than
   bypassing it. Missing mandatory stages or skipped required tests prevent a
   passed rehearsal.
6. Record findings and owners, cleanup of disposable artifacts under the
   approved policy, residual limitations and a technical pass/fail decision.
   Store actual pilot authorization separately with named reviewers, dates and
   content/release revision. Technical success never implies real-participant
   authorization.

## Evidence matrix

Every row is pending execution at this baseline. “Current” identifies
inspectable implementation only. Attach revision-specific evidence to a future
rehearsal record; historic test counts are not fresh acceptance.

| Stage / spec section-16 gate                        | Current basis                                    | Required evidence and unresolved dependency                                                                                                           |
| --------------------------------------------------- | ------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| Scope excludes automated employment decisions       | Spec scope and existing report boundary          | Product owner acknowledgement; no ranking/advance/reject flow; 6B decisions remain external                                                           |
| Reviewed assessment/candidate text                  | Versioned repository content                     | Actual qualified I-O review tied to item/question/algorithm revisions; fixture flags insufficient; 6B/6C/9C                                           |
| Approved privacy, consent, retention, accommodation | Live settings and consent version exist          | Actual privacy review, frozen applicable notice/policy, working contacts, verified rights/accommodation path; 10A/B                                   |
| Deploy, migration, rollback                         | Build and Alembic commands                       | Revision-tagged artifact/schema checks, populated upgrade and compatible rollback/forward repair; 11A/6C                                              |
| Independent login and role approval                 | Auth verifier, immutable profile API             | Recruiter creates/extracts/edits; separate manager reviews/approves; rejected/edited/stale states; 7A–C                                               |
| Delivery and invitation lifecycle                   | Create/revoke API; default delivery fails closed | Captured local mail, valid consent landing, failures/uncertain acceptance/idempotency, no token leakage; 8A/B                                         |
| Consent, decline, complete, skip and recover        | Candidate consent/submit core                    | No questions before consent, decline without assessment, partial skips, storage denied/reload, expired/revoked recovery, honest persistence; 6C/9A/B  |
| Reports require approved/consented input            | Existing report guards                           | Browser generation/read; unapproved/unconsented negative tests; history unchanged; 12A/6C                                                             |
| Every report label has evidence/rule/confidence     | Existing report summaries/drawers                | Exact versioned item/role trace, approved structure cases, insufficient evidence, historical readers; 9C                                              |
| Token, tenant, role restrictions                    | Existing auth/invite API and tests               | Expired/revoked/rotated token rejection, cross-tenant denial, role restrictions, real HTTPS cookies/CSP; 7–8/11B/12A                                  |
| Audit covers sensitive actions                      | Audited endpoints; immutable DB events           | Check creation/read/approval/consent/report/export/deletion chain and PostgreSQL immutability; related-entity lookup limitations explicit             |
| Rights and correction/withdrawal                    | Assessment export/anonymize APIs                 | Verified intake, restricted download, idempotent deletion, derived-report removal; missing lifecycle and correction/withdrawal paths: 10A/B           |
| Cleanup and backlog                                 | One-batch submitted-assessment retention         | Unattended all-category cleanup, multi-batch drain, missed-run/no-progress failure alert; 10C/11A/C                                                   |
| Incident and rotation                               | Single auth/invite keys                          | Safe failure alert received, responder action, old-key rejection/new-key success on all replicas, session/invite recovery; 7A/8A/11C                  |
| Backup/restore and deletion replay                  | No backup/replay tool in baseline                | Encrypted backup, isolated restore, replay post-backup deletion before access, intact control, measured recovery against approved objectives; 10C/11C |
| Accessibility and security                          | Existing unit/component/security work            | Fresh hosted CI/security evidence; real browser automated and manual keyboard/screen-reader/zoom/mobile results; 12A/B                                |
| Training and working support contacts               | Training procedure prepared                      | Attendance, consent/limits comprehension, measured timing, verified support/accommodation route; 12B and accountable owners                           |
| Synthetic end-to-end rehearsal                      | This plan only                                   | All required rows pass at the same release revision with no required skips; 12C technical decision recorded                                           |

## Stop and restart criteria

Stop the affected journey and do not claim release readiness if any of these
occurs:

- Real data, external mail/paid-provider use or unapproved environment appears
  in a synthetic rehearsal.
- Tenant/role boundary, consent, immutable history/audit or approval gate fails;
  credentials, raw links or candidate content appear in telemetry.
- A report's interpretation changes without approved versioning, evidence cannot
  explain a label, or a user treats the output as a hiring decision/prediction.
- A required accessibility path, verified rights/support contact or
  comprehension check fails.
- Migration/rollback compatibility is unknown; restored deleted data is
  readable; deletion journal/replay is incomplete; cleanup leaves unexplained
  overdue records.
- Readiness, alert receipt or required tests fail, or a mandatory stage is
  blocked/skipped.

Keep affected traffic/jobs stopped under 11A controls, record the incident or
blocker, assign an owner and fix/retest the failure. Restart only after the
accountable release/incident owner records authorization and the relevant
evidence passes. No signoff, RTO/RPO, policy deadline or accepted exception is
supplied by this document.

## Future execution record template

Copy into a dated evidence artifact when execution is authorized:

```text
Release SHA / artifact IDs / schema / content versions:
Environment / synthetic fixture set / loopback mailbox:
Operator / UTC start and finish / browsers and devices:
Stage / exact command or manual steps:
Expected / observed / exit code / sanitized artifact path:
Passed / failed / blocked / skipped and reason:
Incident or follow-up owner / disposition:
Technical release decision and accountable owner:
Separate real-participant authorization record (or NOT AUTHORIZED):
```
