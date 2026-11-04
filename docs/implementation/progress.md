# Final implementation coordination

Updated: 2026-11-04. Coordinator Run: `run_7018c5c6a285`.
Integration: `codex/final-implementation`, initial revision `a8de73c5c2d90fb085ef72e95555df8bdfda81e9`.
Protected main baseline: `f5224c9d7d7d6b143bd43c3ca5c77022856cdb90`.

## Operating contract

Only reviewed worker commits integrate here. Dependent workers start from the latest committed integration revision. User scheduling update supersedes the original worker cap: optimize wall-clock completion, initially target 6–8 useful active workers, then scale dynamically with memory/provider capacity and disjoint ownership; there is no fixed cap. Do not launch duplicate or waiting workers. Coordinator owns this ledger, integration and shared-contract/migration allocation. Workers must propose contract shape, compatibility and migration strategy before changes. No schema allocation in the first wave.

Run targeted checks per worker, with broad combined checks at meaningful integration checkpoints; avoid redundant full suites and shared test state. Timebox decision preparation to concrete recommendations and unresolved approvals. Keep reviewers checking finished diffs, integrate continuously, and automatically replace finished workers with newly eligible tasks. Partial preparation or interface-preserving fixes do not satisfy whole-package dependency/acceptance gates.

## Current scheduling and critical path

Capacity check: 24 GiB RAM, memory-pressure tool reports 37% free, 655 GiB disk available. `gpt-6-astra` verified by actual worker tool execution. Expand four active tasks to eight with independent bounded slices.

Engineering critical path: decision record → approved assignment/version contract (6C) → invitation delivery API (8A) and candidate progress (9A/9B) → privacy lifecycle (10A) → full browser integration (12A). Parallel identity path: identity/membership decisions plus 6A → 7A → 7B/7C → 8B, converging at 12A. Hosting/operations path: 11A preparation → configured hosting/runtime (11B/11C) → 10C restore/retention → 12C rehearsal. Actual product/scientific/provider decisions and external review are gates, not elapsed engineering estimates.

Start now without deciding those gates: 9A storage denial/stale-save/receipt fixes preserving current interfaces; 11A provider-neutral packaging of existing Next/FastAPI/PostgreSQL topology; 12A isolated production browser scaffold; 12B audit/checklist/tool preparation; 12C runbook and rehearsal preparation. Split later API/UI tasks only after contract agreement. Keep root dependency files, shared contracts and migrations singly owned.

Synthetic data and controlled local mail only. No push, public deployment, purchases, real email, production secrets or existing database resets. Preserve ports 3000, 8001 and 8000. Each worker uses a separate checkout and isolated database/schema. No scientific or external approval is inferred from implementation authority.

## First wave

All three child worktrees started at committed integration revision `a8de73c`. Branches have prefix `AbhiNutakki/`; worktrees are under `/Users/abhiramnutakki/orca/workspaces/iopsych/`.

| Package/task | Branch | Task / active dispatch | Ownership | Ports / DB | State / evidence |
| --- | --- | --- | --- | --- | --- |
| 6A | `iopsych-6a-setup` | `task_51aea6c0d21e` / `ctx_454cacc97083` | Setup/startup, local synthetic login, focused tests, README, 6A report | 3101 / 8101 / `iopsych_6a`, DB port 5541 | Running; actual agent commands observed; setup hook exit 0 |
| 6B preparation | `iopsych-6b-decisions` | `task_3b6a7f8f3efd` / `ctx_d7fff07517b3` | `6b-decisions.md`, `6b-report.md` only | 3102 / 8102 / `iopsych_6b` reserved | Running; turn_started observed; approvals pending |
| 12A/12B audit | `iopsych-12ab-audit` | `task_7d18dbac142d` / `ctx_03a733782cc2` | Read-only code/test audit; `12ab-audit.md` report only | 3103 / 8103 / `iopsych_audit` reserved | Running; actual code/test inspection observed |

Initial dispatches `ctx_8f1ba11ba1d4`, `ctx_30f32ea5ece7`, `ctx_c6e202ebf48d` failed before task delivery because of Codex's update prompt. Selected “Skip until next version” and retried the same tasks in the same terminals using supported `--retry-of`; no duplicate editors. Those retry turns started but the provider rejected the literal `gpt-6` model for the ChatGPT account. All three were explicitly stopped after inspecting the terminal error. The worker model menu lists GPT-6-Astra as available/default; subsequent starts use `gpt-6-astra`, with actual agent tool execution observed. Audit retry `ctx_e879905cb46c` failed before delivery with `terminal_handle_stale`, then its owned terminal was released through Orca and the same task retried. No task implementation occurred in rejected-model turns. Saved setup: `npm ci && PYTHON_BIN=python3.12 npm run api:install`.

## Package ledger

Expanded wave confirmed eight active workers, all with `turn_started` and requested/effective `gpt-6-astra`. New four worktrees branch from `3602cb0`; runner branched from `8450a09`. Branch names below have `AbhiNutakki/` prefix.

| Slice | Branch | Task / dispatch | Exclusive ownership | Runtime allocation |
| --- | --- | --- | --- | --- |
| 12A early runner | `iopsych-12a-runner` | `task_39bfc496bb85` / `ctx_1102016053c8` | `tests/browser/**`, `scripts/browser-e2e*`, `12a-scaffold.md` | 3104/8104/5544, local mail 1124/8124 |
| 9A compatible storage fixes | `iopsych-9a-storage` | `task_23dde4095af6` / `ctx_75b5d5c7e879` | candidate-storage helper/tests, candidate-assessment component/tests, `9a-report.md` | 3105/8105/5545, `iopsych_9a` |
| 11A packaging preparation | `iopsych-11a-packaging` | `task_1147cce72e78` / `ctx_4d2b01907bbf` | `deploy/**`, app Dockerfiles, `.dockerignore`, `11a-report.md` | 3106/8106/5546, `iopsych_11a` |
| 12B preparation | `iopsych-12b-a11y` | `task_e6bd8f0e591f` / `ctx_2e6f574be424` | `docs/accessibility/**`, `12b-preparation.md`; no app edits | 3107/8107/5547, `iopsych_a11y` |
| 12C preparation | `iopsych-12c-runbooks` | `task_04ff3171b77a` / `ctx_dbef9130a02e` | `docs/operations/**`, `12c-preparation.md` only | 3108/8108/5548, `iopsych_runbooks` |

All report basenames above live under `docs/implementation/`. Setup hooks run concurrently; workers verify completion before tests. Root package/lock files remain 6A/coordinator owned; runner uses an isolated test-tool manifest/lock. Automated axe tooling belongs to runner, manual protocol/evidence to 12B, and current gap inventory to the read-only auditor. Full package acceptance remains pending despite these slices running.

Pending means no acceptance claimed. A prepared decision or scaffold never closes the full package. Revision-linked reports will record exact commands, results, failures/skips and external limitations.

| Package | Dependencies | Owner / status | Acceptance evidence required | Branch / commit / blockers |
| --- | --- | --- | --- | --- |
| 6A setup | Existing foundation | Worker 6A; running | Fresh setup, PostgreSQL migration/seed/tenant verification, actual launcher regression, synthetic login | First-wave branch; commit pending |
| 6B decisions | None | Preparation reviewed/integrated; user/product/I-O decide | Every decision has owner, four structure examples, approved choices and spec reconciliation | Worker `298ce31` → integration `4638236`; actual decisions pending |
| 6C historical versions | 6B for full acceptance | Backend compatibility preparation running | Populated upgrades preserve invites/drafts/submissions/v1 reports; assignment policy | `iopsych-6c-versions`; contract agreement required before shared edits |
| 7A provider/session | 6A, identity choice | Unassigned; gated | Separate identities, callback/claims/expiry/sign-out/redirect negatives | Provider decision/configuration |
| 7B provisioning | 7A, membership choice | Unassigned; gated | Audited grant/change/revoke, deactivation and tenant tests | Dependencies |
| 7C manager workflow | 6B, 7A | Unassigned; gated | Browser handoff/edit/reject/approve, immutable versions, archive permissions | Decisions/dependencies |
| 8A delivery lifecycle | 6C, delivery choice | Unassigned; gated | Local captured delivery, idempotency, uncertainty/commit recovery, secure credentials | Delivery decision; external staging later |
| 8B invitation UI | 8A, 7C | Unassigned; gated | Browser approval-to-invitation, status/permission/error coverage | Dependencies |
| 9A device recovery | 6C for full acceptance | Interface-preserving slice running | Denied/quota storage, truthful saving, incomplete edits, expiry, minimal receipts | `iopsych-9a-storage`; historical assignment integration pending |
| 9B progress/context | 6B, 6C, 9A | Unassigned; gated | Approved promise, persistence/access/version/privacy coverage | Scope decisions |
| 9C evidence/matching | 6B, 6C | Unassigned; gated | Approved four structure extremes, language parity, item-level traces, historical readers | Actual interpretation approval |
| 10A privacy lifecycle | 6B, 6C, 8A, 9B | Unassigned; gated | All lifecycle categories, policy snapshots, rights and PostgreSQL races | Privacy decisions/dependencies |
| 10B privacy admin | 10A, 7B | Unassigned; gated | Bounded discovery, related audit, downloads and rights workflow | Dependencies/verified contacts |
| 10C retention | 10A, 11A scheduler | Unassigned; gated | Backlog drain, missed-run alerts, restore deletion replay | Policy/scheduler/restore |
| 11A packaging | Hosting choice; integrate 6A | Provider-neutral preparation running per user update | Reproducible assets/schema, controlled migrations, graceful shutdown, rollback rehearsal | `iopsych-11a-packaging`; hosting decision; deployment not authorized |
| 11B runtime bounds | 6A, 7A, 8A; staging 11A | Unassigned; gated | Hosted validation, readiness, size/time/concurrency limits, synthetic provider smoke | Dependencies/provider access |
| 11C operations | 11A; integration 8A/11B | Unassigned; gated | Safe correlation/logs/alerts, encrypted backup/restore objectives and rehearsal | Hosting/responders/provider setup |
| 12A E2E | Features 7–10, 11A/11B; scaffold early | Audit integrated; runner worker active | Production browser/PostgreSQL journey and negatives, zero required skips, hosted evidence | Audit `ed41304` → `8bb1016`; full journey dependencies |
| 12B accessibility | Completed screens, 12A; incremental audit early | Audit integrated; preparation worker active | Automated scans plus keyboard/screen-reader/device checks and measured user studies | Manual/user evidence pending; axe owned by runner |
| 12C runbooks/rehearsal | 10C, 11A–C, 12A/B | Documentation preparation running | Revision-linked rehearsal, named owners and actual content/privacy sign-off | External reviews; no approvals claimed |
| 12D demo/handoff | 12A–C technical gates | Unassigned; gated | Controlled synthetic demo, walkthrough, evidence, contribution/license/limitations | Public publication separately authorized |

## Integration evidence

6B documentation commit `298ce31` reviewed, independently passed Prettier and diff checks, integrated as `4638236`. Coverage audit `ed41304` reviewed, independently passed Prettier and diff checks, integrated as `8bb1016`. Both completed workers reported success for their bounded tasks and were released; neither closes full package acceptance. Audit worker reports 104 web tests passing and 127 API tests passing/two PostgreSQL skips under explicitly reduced coverage/cache settings; see report, not a release gate. Existing historical test counts remain baseline context only.

6C backend compatibility task `task_d7602200cf01`, dispatch `ctx_1d41002f09c5`, branch `AbhiNutakki/iopsych-6c-versions` started from `4638236`, with 3110/8110/5550 and `iopsych_6c` reserved. It must obtain coordinator contract/migration agreement before shared edits; frontend will be split after agreement. No scoring change or approval is implied. User questions for provider defaults, journey scope and synthetic-only interpretation are pending asynchronously; independent work continues.

## Shared contract decisions

- 6A additive local contract approved by coordinator in `msg_3e7b0f122730`: fixed synthetic identity selector at `POST /v1/auth/local-login`, short-lived credential exchanged server-side by `POST /api/session/local` into the existing HttpOnly cookie. Default disabled, explicit development policy, loopback peer/host/configured origins, same-origin mutation checks and exact seeded identity/tenant checks required. No provider/scientific decision, migration or shared-package schema change authorized by this approval.
- Docker is available (server 29.8.0); existing `iopsych-postgres-1` on 5432 stays intact. 6A has a separate Compose project/database port 5541 allocation.
