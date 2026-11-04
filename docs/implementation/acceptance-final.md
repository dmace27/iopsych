# Final acceptance reconciliation

## Coordinator follow-up, 23:49 UTC

The historical open reissue defect below is resolved by `5231feb`, with six
regressions first failing and then passing. Native review additionally found
focus loss and duplicate provider landmarks; `1c1d606` fixes both, and the
desktop/mobile exact-fix rerun passes with zero main-scoped axe violations
(`165e51a`). Final web/shared suites pass 643/101 tests; strict typing passes
142 Python files plus web/shared. The affected 38-case production browser retry
passes, with nine earlier green cases separately qualified by revision.
Patched dependency and tracked-source/history secret audits are clean. Final
API/web images build; rollback-only remote experiments pass 18 tests but do not
implement a committing migration bridge. These updates resolve the specific
pending evidence noted below, not the remaining package/external gates. See
`integrated-verification.md` and the latest progress override for exact scope.

## Original independent review

Reviewed `e3d73a7361a69b8343b39409b7c26d090c0a6988` on November 4, 2026. This is
bounded engineering acceptance evidence, not a green release or full package
acceptance. All 21 packages retain their individual final-plan gates. Read the
final plan, current progress overrides, prior
[regression receipt](regression-next.md), frozen
[acceptance review](acceptance-current.md), remote review, browser and
[clean image receipt](packaging-final.md). Web AGENTS and installed Next 16.4.1
client-boundary documentation were read. Live Orca terminal showed
`GPT-6-Astra medium` without Fast; no toggle occurred. Saved setup reported
`__ORCA_SETUP_COMPLETE__:698969f3-d855-4f3b-be0c-29172caf6327:0` before tests.
Only this report and the coordinator-authorized top supersession note in
`6b-decisions.md` change. No app, dependency, migration, database, provider,
listener, deployment or progress-ledger changes occurred.

Evidence limits: clean API/web image builds passed at `5cde2e7`, excluding later
UI/security changes and runtime acceptance. Coordinator reports web 637/shared
101 tests passing with coverage gates and strict typing passing for 141 Python
files plus web/shared. API owner receipt `f02405a` reports 1187 passes/zero
skips at `b13e591`, initially 99.98% branch coverage, then 11 focused appended
tests on unchanged application code reaching 100% (4242 statements, 876
branches). This is explicitly cumulative coverage, not a fresh single-run
aggregate here. Initial browser aggregate remains 37 passed/10 failed; the
38-case affected rerun is pending. Certifi pin `616b861` is implemented; fresh
patched audits and source/history scans remain pending. Remote-lineage
bridge/rollback evidence is partial and owner-held. None of these pending
results is presumed green.

Provider UI review: directly inspected `/tmp/iopsych-provider-desktop.png` and
`/tmp/iopsych-provider-mobile.png`. Text wraps within the pictured layouts;
provider failure, stored revoked state and unknown local delivery are separately
visible. The mobile screenshot includes the focused skip link and development
indicator; it does not prove production keyboard recovery or screen-reader use.
Client parsing requires UUIDs and strict operational fields; proxy changes add
only delivery GET/reissue POST to the existing authenticated boundary. API
delivery/reissue use recruiter/admin authorization and tenant-scoped invitation
lookup. Consent/decline suppress replacement; server also rejects used links. No
new tenant disclosure defect was established by this bounded inspection.

**Confirmed open defect, escalated immediately as `msg_c0ac9b143641`:** in
`provider-delivery.tsx`, an unknown first reissue outcome retains the UUID and
sets global busy, but a same-key retry rejected with 429/401/403 clears both
uncertainty and global busy. Those failures cannot establish whether the first
request committed: the API rate limiter runs before reissue reconciliation.
Refresh/new issuance becomes possible, permitting loss of the unresolved key.
Fix ownership was requested for the component and its test; no app fix is
included here. Keep uncertainty latched until an authoritative reconciliation,
and test unknown→429/401/403→success with the same UUID and workspace lock.

Existing focused checks passed: 12 tests across provider component (8), client
(2), and invitation proxy (2), using an allowlisted environment and Vitest from
`apps/web`, without coverage/full-suite duplication. An initial root invocation
with `--project web` failed discovery (no matching project), then was corrected;
it executed no tests. Existing tests cover confirmation cancellation, same-key
unknown→success, missing provider record and several terminal-state guards.
Missing focused evidence includes workspace-wide unknown latch, archived-role
reissue, deferred response/unmount, multi-row concurrency and native focus after
successful replacement. Focus intent exists in the parent, but it captures the
active element after the async response; browser proof remains required.

| Package | Accepted engineering slice / evidence                                            | Remaining external decisions or approval                                         | Missing tests or incomplete engineering gate                                                                     |
| ------- | -------------------------------------------------------------------------------- | -------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| 6A      | Local setup, safe launcher/login and boundary repairs                            | None for synthetic local setup                                                   | README-only fresh reconciled checkout through start/migrate/seed/login                                           |
| 6B      | Auth0/Resend selected; November 3 direct-v2 product decision recorded            | Organization, hosting, resume/context, notes/review states; I-O/privacy approval | Reconcile remaining conflicting specification promises with accountable decisions                                |
| 6C      | Immutable assignments, retained v1 readers and v2 trace compatibility integrated | Reviewed real-pilot content/retirement eligibility                               | Complete populated supported-history bridge, drafts/reports/hash preservation and rollback evidence              |
| 7A      | Auth0 API/web contracts, local synthetic path and session defenses integrated    | Configured independent provider identities and deployment settings               | Real callback/expiry/recovery/HTTPS-cookie and separate recruiter/manager smoke                                  |
| 7B      | Audited existing-account administration and permission enforcement               | Initial provisioning and organization membership policy                          | Controlled provider-subject provisioning and final cross-tenant/access browser evidence                          |
| 7C      | Metadata/archive, immutable versions and approval controls                       | Manager states and notes destination                                             | Explicit submit/request-edits/reject attribution, stale-state and full revision loop                             |
| 8A      | Separate encrypted local queue and Resend outbox; bounded retry/cancellation     | Verified domain, credentials/key custody, controlled mailbox and operations      | Final lifecycle/concurrency/uncertainty and populated preservation checks; staging delivery                      |
| 8B      | Issuance/revoke plus provider status and confirmed stable-key reissue UI         | 7C and configured delivery gates                                                 | Fix unknown→rejected retry latch; workspace/focus/archived negatives and complete approval-to-invite journey     |
| 9A      | Pinned device recovery, denied-storage and stale-clear repairs                   | Intended-user recovery comprehension                                             | Final candidate browser evidence after integrated notice/visual changes                                          |
| 9B      | Existing device-only interfaces preserved                                        | Explicit server-resume/context promise or approved scope revision                | Server draft/context persistence, access, version and lifecycle integration remain incomplete                    |
| 9C      | Frozen v1 replay and direct-v2 matching/trace integrated                         | Independent interpretation, thresholds, content and scientific approval          | Final dual-language/extreme-case, persisted v1 report/hash/trace evidence                                        |
| 10A     | Notice snapshot/digest, compatible export and serialization locks                | Approved notices, category clocks, rights and draft/context policy               | Non-submitted categories, withdrawal/correction, expired identity verification and upgrade deadline preservation |
| 10B     | Exact discovery and related audit API/UI with stale-feedback repairs             | Verified-contact rights process                                                  | Deleted-report durable lineage, invite-only rights and verified request completion                               |
| 10C     | Bounded drain and local synthetic deletion-replay rehearsal                      | Retention policy, scheduler/alert ownership                                      | Authoritative production journal completeness, unattended scheduling and all-category coverage                   |
| 11A     | Clean images at 5cde2e7, nonroot configuration/revision labels                   | Hosting/TLS/private ingress and runtime/migration privileges                     | Final-source runtime/images, populated bridge and complete rollback/forward-fix rehearsal                        |
| 11B     | Configuration/body/time/readiness/extraction bounds                              | Hosted ingress/provider configuration                                            | Slow synchronous DB isolation, distributed fairness and configured synthetic extraction smoke                    |
| 11C     | Correlation/release logs and local restore proofs                                | Alert responders, encrypted backups and RPO/RTO                                  | Cross-layer redaction, actual alert delivery and measured hosted restore/replay                                  |
| 12A     | Current JS/typing receipts; API cumulative 100%; browser infrastructure          | Hosted CI/release checks and configured staging providers                        | Affected browser rerun, current security scans, populated migration and frozen final aggregate                   |
| 12B     | Prior 72 synthetic renders/keyboard checks; provider screenshots inspected       | Manual screen-reader/device and intended-user studies                            | Current provider reissue focus/recovery, axe/reflow and measured comprehension/timing                            |
| 12C     | Runbooks and isolated local restore rehearsal                                    | Named owners, working contacts, I-O/content/privacy sign-offs                    | Full staging failure/rights/retention/alert/restore rehearsal and training                                       |
| 12D     | Technical receipts and synthetic screenshots available                           | Controlled demo/publication authorization                                        | Reviewer walkthrough, measured handoff/license/contribution/limitations after technical gates                    |

Next actual useful slice: assign the two provider component/test files to one
owner to preserve unknown-outcome state across rejected retries and add the
workspace/native-focus proof. Collect the already-running browser/security and
bridge receipts rather than duplicate their suites. Coordinator alone integrates
and freezes the final gate. Scaffolds, mocks, product decisions and cumulative
coverage do not constitute scientific, privacy, provider or participant
approval.
