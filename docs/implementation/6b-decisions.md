# 6B decision preparation

Prepared 2026-11-04 from `a8de73c`. Status: **recommendations only; every
decision below is pending user/reviewer approval**. Preparation is complete;
package 6B's full acceptance is blocked until actual decisions and authorized
specification updates are recorded. This document does not supersede the root
specifications.

Authority: [final plan](../../final-implementation-plan.md), package 6B;
[product specification](../../mvp-spec.md), sections 3, 5–12, 16–17;
[readiness findings](../../finish.md), tasks 2–4, 7–10, 12, 16.

## Authority, owners, and evidence

The dispatch authorizes documentation and synthetic local work only. It does not
authorize changing scientific interpretation, provider provisioning, real mail,
purchases, public deployment, production secrets, database resets, or pilot use.
No runtime was started for this package. Existing synthetic fixtures and local
mail capture may support later authorized engineering tasks; their review flags
and passing tests are never human content approval.

The user must name the following people. These are accountable decision seats,
not claims that anyone has accepted responsibility or signed off:

| Seat                                   | Accountability                                                                             | Named individual / approval       |
| -------------------------------------- | ------------------------------------------------------------------------------------------ | --------------------------------- |
| Product owner (PO)                     | User appoints scope/pilot decision maker; approves journeys and exclusions                 | Unassigned; pending user          |
| Engineering owner (EO)                 | Integration, contracts, migration compatibility, provider and deployment feasibility       | Unassigned; pending user          |
| Qualified I-O reviewer (IO)            | Construct meaning, all four structure cases, items, thresholds, confidence and questions   | Unassigned; pending user/reviewer |
| Privacy/legal reviewer (PR)            | Pilot purpose, jurisdiction, processors, notice, rights, retention and residency           | Unassigned; pending user/reviewer |
| Operations/security owner (OO)         | Delivery, hosting, backups, incident and retention operations                              | Unassigned; pending user          |
| Pilot administrator/support owner (SO) | Provisioning, rights verification, accommodations, training and external notes destination | Unassigned; pending user          |

The PO is responsible for obtaining named owners before accepting these choices.
Each approval must record decision ID, selected option or replacement, named
approver, date, scope (synthetic engineering or real pilot), exact
document/content revision, evidence link, conditions, and downstream spec
revision. No such approval evidence was supplied. A coordinator merge is not IO
or privacy sign-off.

## Decision register

All rows have status **PENDING**. Recommendations are concrete proposals, not
implementation instructions until accepted by their accountable owner(s).

| ID                   | Recommended choice and tradeoff                                                                                                      | Accountable approval                          | Packages blocked by this choice                |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------- | ---------------------------------------------- |
| D01 structure        | Compare availability directly to preference; retain behavioral definitions; version any changed algorithm                            | PO + IO; EO owns compatibility                | 6C policy, 9C, 12C                             |
| D02 identity         | Clerk-managed internal sign-in, invite-only provisioning; database permissions remain authoritative; candidate links remain separate | EO + PO; PR reviews processor                 | 7A, then 7B/7C and downstream account journeys |
| D03 memberships      | One organization per internal user for MVP; show organization context without a switcher; reject self-service tenant reassignment    | PO + EO                                       | 7B; spec screen conflict                       |
| D04 delivery         | Amazon SES API adapter with durable delivery/recovery design; local capture only during this dispatch                                | EO + OO; PR reviews processor                 | 8A, then 8B/10A                                |
| D05 hosting          | One AWS environment: separate Next.js and FastAPI ECS/Fargate services, private RDS PostgreSQL, single public web origin             | EO + OO + PO; PR approves location/processors | 11A hosting, 11C, 10C                          |
| D06 draft resume     | Retain consent-gated server drafts and cross-device resume through an unexpired invite; truthful local fallback                      | PO + PR; EO approves contract                 | 9B, 10A; 6C draft compatibility policy         |
| D07 optional context | Retain one optional plain-text candidate note, maximum 1,000 characters; no scoring or extraction use                                | PO + PR + IO; EO approves contract            | 9B, 10A, 12C                                   |
| D08 interview notes  | Keep notes in the pilot organization's approved restricted interview-notes repository; no in-app notes in MVP                        | PO + SO + PR                                  | 7C notes acceptance, 12C                       |
| D09 manager states   | Explicit draft → submitted for review → approved / changes requested / rejected, bound to an immutable version                       | PO; EO owns transitions and permissions       | 7C, then 8B                                    |
| D10 privacy policies | Adopt the proposed lifecycle and rights rules below only after jurisdiction-specific review                                          | PR + PO; SO/OO accept operational duties      | 10A–10C, 12C; D04–D08 final policy             |

## D01: structure semantics and four extreme examples

Current section 5 defines role structure as availability of defined goals,
routines and requirements, and candidate structure as preference for predictable
direction. Section 7 simultaneously specifies `abs((6 - R) - C)` and says high
availability satisfies high preference. These statements disagree; the old
formula is not evidence that the alternative has scientific validity.

Recommend `comparison_target = R`, with `abs(R - C)` for structure, keeping
existing proposed distance thresholds (0–1 aligned, 2 worth discussing, 3–4
potential friction) subject to IO approval. The table assumes approved role
input and sufficient evidence. Low-confidence inputs still yield insufficient
evidence; unapproved profiles must not become eligible for report generation.

| Role availability R | Candidate preference C | Current inverse distance / label | Proposed direct distance / label | Proposed plain-language interpretation                                                                                                       |
| ------------------- | ---------------------- | -------------------------------- | -------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| Low (1)             | Low (1)                | 4 / potential friction           | 0 / aligned                      | Few prescribed routines and little preference for predictable direction coincide; this does not establish ability to handle ambiguity.       |
| Low (1)             | High (5)               | 0 / aligned                      | 4 / potential friction           | Little predictable direction is available where it is strongly preferred; ask what support would help.                                       |
| High (5)            | Low (1)                | 0 / aligned                      | 4 / potential friction           | Highly prescribed routines may differ from the person's preference; ask about flexibility and experience without inferring poor performance. |
| High (5)            | High (5)               | 4 / potential friction           | 0 / aligned                      | Defined routines and direction are available where they are strongly preferred; this is not a hiring recommendation.                         |

Alternative for reviewer consideration: retain inversion but explicitly redefine
one scale as the opposite quantity, revising constructs, assessment content,
extraction instructions, labels and examples. This is a larger semantic change;
never relabel stored values as though their meaning had always been different.
The reviewer may also reject symmetric distance or the labels entirely. None of
these alternatives is approved, including for a changed synthetic matcher.

After approval, 6C must pin immutable assignment/scoring definitions, define
reviewed/retired assignment eligibility and legacy backfill, preserve unknown
version failure handling, and retain historical readers. Then 9C must change
both languages, extraction instructions, definitions, fixtures, schemas and
report explanations together under a new algorithm version. Preserve v1 reports
exactly as saved; do not silently recompute or reinterpret them. Test the four
cases, threshold boundaries, skips, confidence, parity, and populated upgrades.
Approval of this formula alone does not approve assessment items or pilot
validity.

## D02–D05: identity, organizations, delivery, hosting

**Identity.** Prefer Clerk over building authentication around the present
manual JWT form. Clerk documents managed authentication and user management;
this is a capability reference, not a procurement or compliance assessment
([official documentation](https://clerk.com/docs)). Use an explicit allowed
issuer/audience/signature contract, server-side verification, safe local
`returnTo`, visible sign-out and expired-session recovery. Link provider
subjects to pre-provisioned database users; never grant organization or manager
access from untrusted client claims. Disabled users and role changes must take
effect on subsequent requests. Synthetic development login remains explicitly
local-only. Alternative: the pilot's existing vetted identity provider, if
required; EO must record its verification and provisioning contract before 7A.

**Memberships.** Keep the current single-organization boundary. This reduces the
migration and tenant-switching surface for the small pilot, but users cannot
work across organizations using one account. No organization switcher or
arbitrary organization selector should imply otherwise. If memberships are
selected instead, coordinate the membership schema, active tenant selection,
authorization and migration before code changes; do not overload the current
user organization ID.

**Delivery.** SES supports sending through an API
([official sending guide](https://docs.aws.amazon.com/ses/latest/dg/send-email.html)).
Recommend a transactionally recorded delivery job dispatched only after
invitation and audit commit, with bounded retries, idempotency, distinct
pending/sent/failed/ unknown outcomes, authenticated event handling and
revocation/reissue policy. Provider acceptance is not inbox delivery. An
uncertain send must not blindly create a new invitation. Never store plaintext
tokens in an outbox: any temporary encrypted delivery credential requires
approved key ownership, least-privilege access, expiry and deletion controls.
This is a proposed design requiring shared contract/migration coordination, not
a change to the current token-storage rule. Alternative: an equivalent
transactional provider if existing procurement favors it. Validate sender
domain, recipient restrictions, bounce handling, retention and cost before
approval. Do not send real messages during preparation.

**Hosting.** Prefer the single-cloud alternative already allowed by spec
section 8. Fargate supports container workloads with explicit networking and IAM
policies
([official guide](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/AWS_Fargate.html)).
Propose `ca-central-1` for review, not as a claim about pilot jurisdiction or
complete data residency. EO must verify regional service availability and costs;
PR must approve all processor and cross-border paths, including Clerk and email.
Use TLS ingress to the web service, private API access from the web service,
private database networking, separate staging/pilot accounts or isolated stacks,
secret injection, separate runtime/migration privileges, controlled one-time
migrations, scheduled cleanup and encrypted backups. Include shared Python and
versioned definition assets in images. PO/OO must supply a domain, budget
ceiling and accountable responder before provisioning. Alternative: Vercel plus
managed API/database hosting; it simplifies web operations but adds
network/provider boundaries. No deployment, domain purchase or region commitment
is made here.

## D06–D09: journey choices

**Resume.** Preserve the specified `/responses` journey rather than silently
narrowing it to one browser. Propose server saves only after consent, pinned to
invite/definition/scoring versions, with revision conflicts and idempotency.
Cross-device resume requires the still-valid invite credential; do not promise
recovery after expiry or revocation. Show server-save confirmation only after
acknowledgment, explain unsaved in-memory edits and local fallback, and provide
clear-device/save-exit actions. A shared-device mode should avoid persistent
local answers. Submission clears drafts and leaves only an expiring answer-free
receipt. Alternative device-only resume requires explicit PO scope reduction and
updates to sections 10, 11, 13 and package 2C; present behavior is not that
approval.

**Context.** A candidate may leave the optional note empty without penalty.
Label it as context for the human interview, warn against sensitive personal
details, and restrict access to authorized role/report readers. Preserve
submitted context with the immutable assessment, display separately from derived
results, and cover it in notice, export, correction and deletion. Never send it
to the job-description LLM or use it for scores, classifications, confidence or
ranking. Alternative: omit context only after an explicit scope revision of
sections 3 and 9. No note field/API contract is added by this document.

**Notes.** Recommend external notes to avoid building a second candidate-data
system. SO must name the exact organization-owned destination, access group,
retention owner, rights workflow and candidate-reference convention; destination
is currently **unselected and unapproved**. Do not use personal documents, copy
raw invite URLs, or place notes/dispositions inside immutable reports. Until the
destination is approved, the notes journey remains incomplete. Alternative:
in-app notes require separate editable, audited records and privacy coverage,
with an explicitly coordinated contract/migration package.

**Manager review.** A recruiter submits a specific immutable profile revision;
only an authorized hiring manager may approve it. A manager can request changes
or reject with a required reason and actor/time attribution. Proposed
transitions:

| From                         | Action and next state                        | Required guard                                         |
| ---------------------------- | -------------------------------------------- | ------------------------------------------------------ |
| Draft                        | Recruiter submits → submitted for review     | Complete ratings/evidence; exact current revision      |
| Submitted for review         | Manager approves → approved                  | Manager permission; no stale revision; freeze approval |
| Submitted for review         | Manager requests changes → changes requested | Nonempty actionable reason; audit                      |
| Submitted for review         | Manager rejects → rejected                   | Nonempty reason; no invitation eligibility             |
| Changes requested / rejected | Recruiter creates new revision → draft       | Preserve prior decision/reason; explicit resubmission  |
| Approved                     | Edit creates new draft revision              | Approved historical version remains immutable          |

Stale review actions fail rather than approving a different version. Preserve
superseded history without equating it with rejection. Archival is role
lifecycle, not a manager review decision: prohibit new invitations to archived
roles while preserving historical access under policy. Invitations use
explicitly approved versions; a later draft is never automatically approved.
Require a separate manager identity for the pilot handoff; final permission and
state contracts need EO coordination. Include metadata editing and archival in
7C rather than silently omitting existing specified journeys.

## D10: proposed privacy policy for review

These are proposed operational defaults for review, **not approved privacy
policy or jurisdiction-specific legal advice**. PR must determine applicable
obligations, exceptions and final notice language. All periods below are elapsed
UTC periods; configuration changes must not silently extend previously promised
deadlines.

| Category                                                   | Proposed clock and action                                                                                                             | Owner / pending approval |
| ---------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- | ------------------------ |
| Unopened/opened, never consented                           | Invite expires 7 days after issuance; delete identifying invitation data within 24 hours of expiry                                    | PR + PO; OO implements   |
| Declined or revoked                                        | Disable access immediately; delete identifying invite/draft data within 24 hours of event                                             | PR + PO                  |
| Consented but unsubmitted, including server drafts/context | Delete at invite expiry plus at most 24 hours; no indefinite draft retention                                                          | PR + PO                  |
| Submitted answers, context, scores and derived reports     | Retain at most 30 days from submission; delete/anonymize within 24 hours after deadline or earlier verified deletion/withdrawal       | PR + PO                  |
| Device data                                                | Draft TTL no later than invite expiry; clear on successful submission/clear-device; answer-free receipt TTL 24 hours                  | PR + PO; EO implements   |
| Exports                                                    | Short-lived protected download, maximum 24 hours; audit access and expiry, no email attachment                                        | PR + SO                  |
| Non-identifying audit events                               | Proposed 90-day retention; strip candidate content and identifying links when deleting subject data                                   | PR + OO                  |
| Backups and deletion tombstones                            | Proposed backup window 30 days; retain minimal restricted tombstones until all affected backups expire; replay before restored access | PR + OO                  |
| External interview notes                                   | Proposed same 30-day submission-based maximum, earlier rights deletion propagated by SO; destination policy must be approved          | PR + SO                  |

Do not promise remote erasure of offline browser storage or downloaded exports.
Explain these limits, use minimal device data, and clear expired local records
on next access. Resolve backup/audit exceptions explicitly with PR before
acceptance; immutable audit protections do not justify indefinite identifying
data.

Proposed rights and consent rules:

- Snapshot actual purpose, notice text, policy version, contacts and applicable
  retention rules at assignment/consent; retain consent evidence under the
  approved policy. Policy changes require explicit handling, not live-copy
  drift.
- Decline prevents assessment access. Withdrawal after consent is a distinct
  request: immediately suspend further use, revoke links, invalidate access to
  derived reports and initiate deletion under the approved workflow. Do not
  imply that an earlier viewed report or an employment decision can be undone.
- A working support channel remains available after invite expiry. SO verifies
  control of the original address using a fresh bounded challenge or a
  documented alternative reviewed by PR; never require an expired invite token
  or request unnecessary government ID. Log verification outcome without storing
  secrets.
- Acknowledge rights requests within two business days; propose completion
  within seven calendar days of verification, subject to PR-approved statutory
  deadlines and exceptions. Export all covered
  invitation/consent/draft/context/submission/ report data; deletion must cover
  related objects and external notes as applicable.
- Corrections create an attributed amendment or a new consented
  assessment/version; never overwrite immutable historical scores or reports.
  Restrict disputed report use pending review, and expose supersession clearly.
  IO/PO must approve how a new response may generate a replacement report.
- Identify the pilot organization, role family, actual privacy/accommodation
  contacts and responsible human reviewer before real use. No protected-trait
  inference, automated advancement/rejection, composite scores or ranking.
- OO schedules bounded multi-batch cleanup, monitors overdue data, rehearses
  deletion/report-generation races and restores with tombstone replay; SO owns
  requests and accommodations. Real pilot authorization also requires training,
  content review and revision-linked 12C sign-off.

## Specification reconciliation and dependency gate

The worker may edit only these two 6B documents. Root text remains unchanged and
conflicts remain open. After actual approval, the integration owner must make a
separately authorized specification change, with acceptance criteria:

| Decision | Root text requiring reconciliation                                                |
| -------- | --------------------------------------------------------------------------------- |
| D01      | Spec sections 5, 7, 14 and package 3A inverse-rule acceptance; finish task 2      |
| D02–D05  | Spec sections 8–12; account/switcher wording in section 11; finish tasks 3, 4, 12 |
| D06–D08  | Spec sections 3, 9–11, 13 and packages 2C/4B; finish tasks 9–10                   |
| D09      | Spec sections 3, 6, 9–11 and package 1B; finish task 9                            |
| D10      | Spec sections 2, 9–13, 16 and package 4B; finish tasks 10, 13, 16                 |

No shared contracts or migrations were changed. Future owners must ask the
coordinator before editing them, providing proposed shapes, compatibility
impact, backfill/migration and test strategy. This document is not contract
approval.

**Next eligible work:** obtain named-owner decisions and reconcile
specifications. 6A may proceed independently under its existing authorization.
Per the final plan, 11A initial packaging may start after 6A; 12A runner
scaffolding and incremental 12B audits may start where their own prerequisites
hold. Neither exception selects a provider or clears release gates. Full 6C
remains dependent on completed 6B; 7A requires 6A plus accepted D02; 7B requires
7A plus D03; 7C requires 6B and 7A; 8A requires 6C plus D04; 9B/9C and 10A
require their listed upstream packages and accepted decisions. There is no newly
authorized implementation package from this preparation alone. Real participants
remain blocked pending 12C approval.
