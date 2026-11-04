# Support, accommodations, rights and training

Support/accommodation lead, privacy administrator, privacy/legal reviewer and
training lead: owner-unassigned. Example `.invalid` contacts are placeholders,
not working support. Replacing and verifying the contacts is a release gate.
Identity verification, policy, notes destination and interpretation decisions
belong to 6B/10A and accountable reviewers.

## Support and accommodation intake

1. Receive the request through the future verified private contact route. Give
   it a restricted case reference; record only necessary symptom,
   browser/device, UTC time, affected step and preferred accessible response
   channel. Do not ask for a forwarded invitation link, answers, credentials,
   diagnosis or medical history.
2. For sign-in problems, verify environment/account context without requesting
   tokens. For an expired/revoked invite, use authorized tenant discovery once
   8A/10B supplies it; do not extend expiry in SQL or assume the link proves
   identity. Missing discovery is a blocker, not permission to bypass tenant
   controls.
3. For storage/reload problems, explain that current resume is device-local and
   may fail; do not promise cross-device recovery. Have the user retain their
   current page until a support plan is agreed. Browser clearing can discard
   unfinished answers. Server anonymization cannot clear an offline device;
   9A/9B must establish truthful cleanup/resume behavior.
4. For an accessibility barrier, pause the affected journey and route to the
   accommodation lead. Agree an accessible way to communicate and a
   reviewer-approved alternative before continuing. Do not alter assessment
   wording/scoring, supply answers, promise an unapproved alternative or infer
   protected traits. If no accessible path exists, do not proceed with real
   participation.
5. Verify resolution with the requester through the approved channel, record
   remaining barrier and route reproducible synthetic steps to engineering/12B.
   Keep accommodation details out of reports and broad tickets. Contact routing,
   response targets and case retention need actual owner approval.

## Current rights operations

Current implementation: [privacy router](../../apps/api/app/privacy/router.py),
[service](../../apps/api/app/privacy/service.py) and admin web page `/privacy`.
Internal APIs below require an authenticated administrator in the owning
organization. The web proxy uses `/api/internal/…` in place of `/v1/…` and
enforces same-origin mutation checks. Use the admin UI/session rather than
copying bearer credentials into shell history.

| Operation        | Existing API                                             | Check                                                                                         |
| ---------------- | -------------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| Export           | `POST /v1/candidates/{assessment_id}/export`             | JSON attachment, `Cache-Control: no-store`; restricted storage and verified delivery required |
| Anonymize        | `DELETE /v1/candidates/{assessment_id}`                  | `anonymized_at`, `already_anonymized`, `reports_deleted`; second request is idempotent        |
| Retention status | `GET /v1/privacy/status`                                 | Submitted-assessment cleanup coverage is limited; see recovery procedure                      |
| Audit lookup     | `GET /v1/privacy/audit-events?limit=50&entity_id={uuid}` | Exact entity filter, tenant-scoped; limit maximum 200, with pagination                        |

Procedure for synthetic rehearsal now, and real requests only after
policy/verification gates:

1. Record request type and case reference. Privacy reviewer supplies the
   identity/authority verification method, including expired-link requests, and
   applicable response deadline. Do not export/delete until verified. Lack of a
   documented method blocks fulfilment; escalate to the reviewer and keep the
   case open.
2. Authorized administrator confirms tenant and assessment reference through an
   approved discovery process. Current UI requires an assessment UUID;
   no-assessment records and usable discovery remain 10A/10B gaps. Do not guess
   UUIDs or use raw database edits as a rights workflow.
3. For export, retrieve once, verify tenant and intended record in the
   restricted workspace, and deliver only through the approved private channel.
   Do not attach the export to a general issue or email it using this rehearsal.
   Record completion/audit reference, not payload; export-copy
   disposal/retention requires the approved policy.
4. For deletion, confirm verified scope and applicable policy, invoke
   anonymization, then verify reports are removed, candidate payloads replaced,
   invitation email anonymized, token invalidated and audit tombstone present. A
   later export should report `candidate_data_anonymized`. Repeat deletion
   should report already anonymized. Do not delete immutable audit history to
   make counts zero.
5. Record limitations: consent/audit records remain; device copies, previously
   delivered exports and backups are separate boundaries. Follow
   [retention/recovery](retention-recovery.md). Do not tell a requester that all
   copies everywhere were erased on the strength of one API response.

## Correction, withdrawal and pre-submission cases (gated)

There is no correction or withdrawal API at this baseline. Initial decline is
not later withdrawal; revoking an invite is not equivalent to deleting candidate
data. Immutable submitted answers, approved profiles and persisted reports must
not be silently overwritten.

Capture the requested correction/withdrawal in the private case without
reproducing answers in an ordinary ticket, verify identity under the approved
process, and route to privacy/product owners. They must determine scope,
restrictions on continued use, notification, historical record treatment and
whether a new consented assessment is appropriate. Engineering implements the
agreed 10A/10B path and tests its audits/derived-report handling before
execution. Leave the request visibly unresolved until the approved remedy is
verified. For unopened, declined, expired, revoked or consented-but-unsubmitted
invitations without assessments, the current assessment-ID rights endpoints do
not provide complete coverage; do not report success or substitute an unrelated
delete.

## Synthetic user-training session

1. Recruiter creates a synthetic role and inspects quoted extraction evidence.
   Manager uses a separate identity to review/approve a version; an extracted
   draft is never approval. Full handoff depends on 7A–C/8B.
2. Candidate practises reading consent, declining, requesting accommodation,
   skipping and completing. Explain actual device persistence and privacy
   contacts without promising future features. Collect no real candidate
   answers.
3. Recruiter opens a synthetic report and its evidence. Teach that this is an
   unvalidated usability instrument for human interview preparation, with no
   aggregate fit score, ranking, automated advancement/rejection or
   performance-prediction claim. “Worth discussing” is not “not qualified”;
   confidence is not calibrated probability. Do not resolve the structure
   interpretation conflict in training; approved 6B/9C content is required
   before pilot use.
4. Practise a neutral evidence-seeking interview question and handling
   insufficient evidence. Keep notes only in the destination approved through
   6B, never in immutable system-derived reports or an invented notes store.
5. Admin practises verified synthetic export/anonymization; support practises an
   expired link, a storage failure and an accessibility barrier. Use controlled
   local evidence only.
6. Record release/content revision, trainer, participants, date, tasks
   completed, observed comprehension errors and follow-up. Ask trainees to
   explain consent, decline, confidence and “worth discussing” in their own
   words. Measure completion time and comprehension with 12B; do not fabricate
   attendance, measured success or signoff. Failure to explain the limits blocks
   readiness and requires retraining.
