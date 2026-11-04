# Final implementation coordination

Updated: 2026-11-04. Coordinator Run: `run_7018c5c6a285`.
Integration: `codex/final-implementation`, initial revision `a8de73c5c2d90fb085ef72e95555df8bdfda81e9`.
Protected main baseline: `f5224c9d7d7d6b143bd43c3ca5c77022856cdb90`.

## Operating contract

Only reviewed worker commits integrate here. Dependent workers start from the latest committed integration revision. Maximum three implementation workers plus one read-only reviewer. Coordinator owns this ledger, integration and shared-contract/migration allocation. Workers must propose contract shape, compatibility and migration strategy before changes. No schema allocation in the first wave.

Synthetic data and controlled local mail only. No push, public deployment, purchases, real email, production secrets or existing database resets. Preserve ports 3000, 8001 and 8000. Each worker uses a separate checkout and isolated database/schema. No scientific or external approval is inferred from implementation authority.

## First wave

All three child worktrees started at committed integration revision `a8de73c`. Branches have prefix `AbhiNutakki/`; worktrees are under `/Users/abhiramnutakki/orca/workspaces/iopsych/`.

| Package/task | Branch | Task / active dispatch | Ownership | Ports / DB | State / evidence |
| --- | --- | --- | --- | --- | --- |
| 6A | `iopsych-6a-setup` | `task_51aea6c0d21e` / `ctx_5ded07118e01` | Setup/startup, local synthetic login, focused tests, README, 6A report | 3101 / 8101 / `iopsych_6a` | Running; turn_started observed; setup hook exit 0 |
| 6B preparation | `iopsych-6b-decisions` | `task_3b6a7f8f3efd` / `ctx_1babfcadade6` | `6b-decisions.md`, `6b-report.md` only | 3102 / 8102 / `iopsych_6b` reserved | Running; turn_started observed; approvals pending |
| 12A/12B audit | `iopsych-12ab-audit` | `task_7d18dbac142d` / `ctx_a4ea32dc2ba5` | Read-only code/test audit; `12ab-audit.md` report only | 3103 / 8103 / `iopsych_audit` reserved | Running; turn_started observed |

Initial dispatches `ctx_8f1ba11ba1d4`, `ctx_30f32ea5ece7`, `ctx_c6e202ebf48d` failed before task delivery because of Codex's update prompt. Selected “Skip until next version” and retried the same tasks in the same terminals using supported `--retry-of`; no duplicate editors. Original launch receipts confirm requested/effective `gpt-6`; reused terminals retain that model. Saved setup: `npm ci && PYTHON_BIN=python3.12 npm run api:install`.

## Package ledger

Pending means no acceptance claimed. A prepared decision or scaffold never closes the full package. Revision-linked reports will record exact commands, results, failures/skips and external limitations.

| Package | Dependencies | Owner / status | Acceptance evidence required | Branch / commit / blockers |
| --- | --- | --- | --- | --- |
| 6A setup | Existing foundation | Worker 6A; running | Fresh setup, PostgreSQL migration/seed/tenant verification, actual launcher regression, synthetic login | First-wave branch; commit pending |
| 6B decisions | None | Worker 6B prepares; user/product/I-O decide | Every decision has owner, four structure examples, approved choices and spec reconciliation | First-wave branch; decisions pending |
| 6C historical versions | 6B | Unassigned; gated | Populated upgrades preserve invites/drafts/submissions/v1 reports; assignment policy | Decision gate; no commit |
| 7A provider/session | 6A, identity choice | Unassigned; gated | Separate identities, callback/claims/expiry/sign-out/redirect negatives | Provider decision/configuration |
| 7B provisioning | 7A, membership choice | Unassigned; gated | Audited grant/change/revoke, deactivation and tenant tests | Dependencies |
| 7C manager workflow | 6B, 7A | Unassigned; gated | Browser handoff/edit/reject/approve, immutable versions, archive permissions | Decisions/dependencies |
| 8A delivery lifecycle | 6C, delivery choice | Unassigned; gated | Local captured delivery, idempotency, uncertainty/commit recovery, secure credentials | Delivery decision; external staging later |
| 8B invitation UI | 8A, 7C | Unassigned; gated | Browser approval-to-invitation, status/permission/error coverage | Dependencies |
| 9A device recovery | 6C | Unassigned; gated | Denied/quota storage, truthful saving, incomplete edits, expiry, minimal receipts | Historical assignment contract |
| 9B progress/context | 6B, 6C, 9A | Unassigned; gated | Approved promise, persistence/access/version/privacy coverage | Scope decisions |
| 9C evidence/matching | 6B, 6C | Unassigned; gated | Approved four structure extremes, language parity, item-level traces, historical readers | Actual interpretation approval |
| 10A privacy lifecycle | 6B, 6C, 8A, 9B | Unassigned; gated | All lifecycle categories, policy snapshots, rights and PostgreSQL races | Privacy decisions/dependencies |
| 10B privacy admin | 10A, 7B | Unassigned; gated | Bounded discovery, related audit, downloads and rights workflow | Dependencies/verified contacts |
| 10C retention | 10A, 11A scheduler | Unassigned; gated | Backlog drain, missed-run alerts, restore deletion replay | Policy/scheduler/restore |
| 11A packaging | Hosting choice; initial packaging after 6A | Unassigned; pending | Reproducible assets/schema, controlled migrations, graceful shutdown, rollback rehearsal | Hosting decision; deployment not authorized |
| 11B runtime bounds | 6A, 7A, 8A; staging 11A | Unassigned; gated | Hosted validation, readiness, size/time/concurrency limits, synthetic provider smoke | Dependencies/provider access |
| 11C operations | 11A; integration 8A/11B | Unassigned; gated | Safe correlation/logs/alerts, encrypted backup/restore objectives and rehearsal | Hosting/responders/provider setup |
| 12A E2E | Features 7–10, 11A/11B; scaffold early | Audit worker then implementation owner TBD | Production browser/PostgreSQL journey and negatives, zero required skips, hosted evidence | First-wave audit; full journey dependencies |
| 12B accessibility | Completed screens, 12A; incremental audit early | Audit worker then implementation owner TBD | Automated scans plus keyboard/screen-reader/device checks and measured user studies | First-wave audit; human evidence pending |
| 12C runbooks/rehearsal | 10C, 11A–C, 12A/B | Unassigned; gated | Revision-linked rehearsal, named owners and actual content/privacy sign-off | External reviews; no approvals claimed |
| 12D demo/handoff | 12A–C technical gates | Unassigned; gated | Controlled synthetic demo, walkthrough, evidence, contribution/license/limitations | Public publication separately authorized |

## Integration evidence

No implementation commits integrated yet. Existing historical test counts are baseline context only, not current acceptance. Read worker reports, review diffs, independently verify relevant checks, integrate on this branch, then update this ledger and dispatch eligible packages.
