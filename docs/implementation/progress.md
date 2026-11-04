# Final implementation coordination

Updated: 2026-11-04. Coordinator Run: `run_7018c5c6a285`.
Integration: `codex/final-implementation`, initial revision `a8de73c5c2d90fb085ef72e95555df8bdfda81e9`.
Protected main baseline: `f5224c9d7d7d6b143bd43c3ca5c77022856cdb90`.

## Operating contract

Only reviewed worker commits integrate here. Dependent workers start from the latest committed integration revision. User scheduling update supersedes the original worker cap: optimize wall-clock completion, initially target 6–8 useful active workers, then scale dynamically with memory/provider capacity and disjoint ownership; there is no fixed cap. Do not launch duplicate or waiting workers. Coordinator owns this ledger, integration and shared-contract/migration allocation. Workers must propose contract shape, compatibility and migration strategy before changes. No schema allocation in the first wave.

Run targeted checks per worker, with broad combined checks at meaningful integration checkpoints; avoid redundant full suites and shared test state. Timebox decision preparation to concrete recommendations and unresolved approvals. Keep reviewers checking finished diffs, integrate continuously, and automatically replace finished workers with newly eligible tasks. Partial preparation or interface-preserving fixes do not satisfy whole-package dependency/acceptance gates.

### Fast service policy

User explicitly authorizes actual Fast service mode and its higher usage rate, not Ultrafast or purchases. Coordinator priority mode was enabled and verified by the user; do not toggle it. Installed Codex schema exposes `service_tier` config and `serviceTier` session settings; current user default is `service_tier = "fast"`. Defaults alone are not live-session evidence. On 2026-11-04, supported Orca terminal `/fast` control produced **“Service tier set to priority”** and a **fast** status bar in four existing sessions: 6C backend (`ctx_1d41002f09c5`), 6A reviewer (`ctx_e8df940ba05d`), security assessment (`ctx_6e423bb1f5c7`), and runbooks (`ctx_dbef9130a02e`, which completed during the setting change). Three remained working after verification, with no interrupted task turn or unsupported session observed. Completed workers are released, not restarted just to change settings.

Future launches must inherit the verified Fast default and have their own live status inspected; if absent, apply `/fast` once through supported control and verify the priority confirmation. Never blindly toggle an already-fast session. Preserve worker work and resume any setting-interrupted task. Continue maximal useful parallel implementation/review/integration after mode checks.

## Current scheduling and critical path

### Latest checkpoint: 22:53 UTC

This checkpoint supersedes all older live ownership and package-status rows below. Accelerated schedule is committed as `3cf79c2`; all original acceptance criteria remain. Integration is `cd113de`. Main is unchanged. The two-hour target still ends 00:31 UTC; reserve 23:46–00:31 for final combined checks, repairs and truthful handoff rather than adding speculative scope.

- Reviewed/integrated since the prior checkpoint: DB deadlines/readiness `0717428`; historical trace backend `9e4bfe7`/`0f0e9e1`/`84e3285` and UI `8b7625c`; session navigation `30ff4dd`; extraction redirect protection `4e97d2f`; safe telemetry `bc90237`; bounded invitation discovery `e6a39f4`; bounded retention drain `cd113de`.
- Independent coordinator evidence: readiness 43 passed/3 PostgreSQL skips; trace backend 60 passed/1 PostgreSQL skip; trace UI 55 passed; navigation 61 passed; redirect safety 80 passed; telemetry 53 passed; invitation discovery 29 passed; retention drain 23 passed. Worker PostgreSQL evidence is separately documented, not substituted for coordinator runs.
- Actual isolated PostgreSQL upgrade/concurrency verification: 44 passed/zero skips, report `531c380`. Production browser checkpoint: 11 passed/zero skips, 27 axe scans without violations, reports `df2ab0c` and associated fixture commits. New accessibility matrix has real failures: 320px overflow and Create role Cancel focus loss; dedicated correction owns app changes while audit retains tests/runtime. Earlier green smoke is not full accessibility acceptance.
- 6A boundary fixes and 6C backend/UI are integrated/reviewed, not still active as historical rows suggest. 7A session improvements, 8A local adapter/discovery, 8B list/revoke UI, 9A pinned recovery, 9C historical trace, 10A export locking, 10C bounded drain and 11A–C local runtime slices are partial engineering completion only. Provider identity/delivery, provisioning, manager workflow, server drafts/context, comprehensive privacy lifecycle/admin and scientific interpretation gates remain open. No full gated package is declared accepted.

| Current task | Dispatch / child branch suffix | Ownership / allocation |
| --- | --- | --- |
| Accessibility matrix | `ctx_2200ba5fbc72` / `iopsych-a11y-matrix` | Browser accessibility spec/report; exclusive 3116/8116/5556/1136/8136 |
| Invitation list/revoke UI | `ctx_7e14cc9f9cf1` / `iopsych-invite-ui` | New client/contracts/UI, proxy allowlist, role link; 3140/8160/5580 |
| Combined regression | `ctx_3848fc7fba6d` / `iopsych-current-regression` | Read-only app, frozen `e6a39f4`; isolated upgrade PG5571; no browser runtime |
| Independent review | `ctx_43d065e44ab0` / `iopsych-latest-review` | Read-only trace/telemetry/discovery/privacy/session review; 3142/8162/5582 |
| Accessibility corrections | `ctx_b081756b1bae` / `iopsych-a11y-fixes` | App CSS/layout and Create role focus, not browser specs; 3143/8163/5583 |
| Privacy discovery | `iopsych-privacy-discovery` | Additive admin-only exact-reference lookup; contract approval before implementation; 3144/8164/5584 |
| Local restore rehearsal | `iopsych-local-restore` | Isolated synthetic script/evidence only; 3145/8165/5585 |

Five workers were executing and two starting at refill. Four new executing screens plus continuing audit show Fast; verify the final two live screens after launch before claiming seven verified. No unsupported session observed. Future workers retain the same verify-not-toggle policy. Coordinator remains sole integrator/migration/dependency owner. Latest completed workers were released after reports; no work was lost for settings.

Critical path now: resolve measured accessibility failures → rerun matrix; finish invitation UI against committed discovery wire → targeted tests/browser handoff; approve privacy lookup engineering contract → backend → separately owned UI. Regression/review and isolated restore proceed independently. No worker waits for an entire phase. Provider/product/privacy/scientific decisions are still unanswered; prepare safe interfaces only, never fabricate approvals. Reserve full release/manual/hosted gates as remaining work even if local slices finish within the target.

### Historical checkpoint: 22:46 UTC

This checkpoint supersedes earlier live-worker counts and ownership tables. Integration `c78a70c` includes 6C integrity repair `beec1c4`, expanded browser suite `7d89b17`/`8caf297`, secure sign-out `fb7a404`, candidate recovery `a8feb7f`, safe upgrade target guard `6619167`, and export/anonymization locking `c78a70c`. Completed workers were released after processing reports. Main remains `f5224c9`; no pushes/deployments/real mail occurred.

- Coordinator independently reran registry 37, sign-out 20, candidate/storage 29 and upgrade-guard 37 tests, all passing. Privacy locking has worker evidence of seven actual PostgreSQL/privacy tests, zero skips; independent PostgreSQL rerun is active.
- Frozen broad check at `4c7caf3`: formatting/lint/types/schema parity/build passed; web 174, shared TypeScript 99, Python contracts 93 passed. API 319 passed, one SMTP skip, one setup error caused by the old fixed upgrade allocation; command failed, not accepted. The SMTP case subsequently passed against controlled Mailpit. Upgrade guard is now corrected; incremental actual PostgreSQL verification is assigned separately. Report integrated `d498b80`.
- Clean-export container builds at `4c7caf3` passed non-root/runtime/asset checks, empty and seven-state populated 0007→0008 upgrades, shutdown and persistence; report `e760e4a`. This is neither hosted deployment nor rollback acceptance. Later readiness/telemetry changes require updated verification.
- Browser owner reports ten production Chromium cases passing with zero skips at child revision `0dbb95e` (integration `fb7a404` plus pinned synthetic fixture). Sign-out and profile contrast regressions now pass. Clear-at-review coverage and newer integration rerun continue; the earlier red run remains preserved, not rewritten as green.
- Engineering contracts approved for DB timeout/pool/schema readiness and safe generated correlation/allowlisted telemetry; no provider or privacy policy approval inferred. User provider/scope decisions remain unanswered. Four newest session screens and all continuing sessions show Fast; no unsupported mode sessions.

| Current task | Dispatch | Ownership / allocation |
| --- | --- | --- |
| Trace backend | `ctx_055f6c35334f` | Report trace backend and canonical fixtures; 3126/8126/5566 |
| Trace frontend | `ctx_22fa434f26b8` | Report drawer/parser/client/internal trace proxy; 3127/8127/5567 |
| Browser integration | `ctx_737f67ec8e78` | Runner/fixtures/tests; released allocation 3116/8116/5556/1136/8136 transferred exclusively |
| DB deadlines/schema readiness | `ctx_e8c966f977cf` | Database config/session, runtime health/tests; 3133/8133/5573 |
| Safe telemetry | `ctx_1d11c9ac4d02` | Runtime telemetry, main middleware wiring, security error header/tests; 3134/8134/5574 |
| Session navigation | `ctx_d6296cd28ef2` | Header/sign-in/safe-return helper; no provider selection; 3135/8135/5575 |
| Boundary review | `ctx_55f2cb0845c4` | Read-only runtime/historical-boundary review; 3136/8166/5576 (8136 belongs to browser mail) |
| Incremental PostgreSQL verification | `ctx_ccb66e632c3c` | Read-only focused upgrades/concurrency/privacy checks; fresh 5571/iopsych_regression and 5568/iopsych_privacy_lock |
| Bounded invite discovery | `ctx_6b93f9587b5a` | Invitation router/schema/new discovery module/tests; 3138/8138/5578 |

Eight tasks were ready and discovery was starting at the last fleet snapshot; all nine session screens show Fast. New work starts from `c78a70c`; DB/telemetry/browser started at `8caf297`. Memory free 48% at latest capacity check. Invite discovery is an approved additive GET-only bounded list preserving current issuance/revoke/candidate responses and current admin/recruiter permissions; no outbox/provider claims. No second worker owns its files. Next eligible work: integrate trace backend before frontend, attach exact fixtures, review readiness/telemetry, then fresh combined regression at a frozen integrated revision. Broader accounts, durable delivery, privacy policy/drafts, scientific changes, hosted/manual/pilot gates remain open.

Capacity check at 22:31 UTC: 24 GiB RAM, memory-pressure tool reports 54% free; earlier disk check 655 GiB available. `gpt-6-astra` verified by actual worker tool execution. Seven workers are executing and five additional disjoint slices are launching; recheck actual readiness and memory before further expansion.

Engineering critical path: decision record → approved assignment/version contract (6C) → invitation delivery API (8A) and candidate progress (9A/9B) → privacy lifecycle (10A) → full browser integration (12A). Parallel identity path: identity/membership decisions plus 6A → 7A → 7B/7C → 8B, converging at 12A. Hosting/operations path: 11A preparation → configured hosting/runtime (11B/11C) → 10C restore/retention → 12C rehearsal. Actual product/scientific/provider decisions and external review are gates, not elapsed engineering estimates.

The earlier 9A storage, 11A packaging, 12A runner, 12B preparation and 12C runbook slices are now integrated, not still running. 6C API/UI split is dispatched against the agreed definition envelope. Root dependencies belong exclusively to security-remediation; migration `20261104_0008` belongs exclusively to 6C backend; coordinator integrates.

### Two-hour execution window

Target: **2026-11-04 22:31 through 2026-11-05 00:31 UTC** (17:31–19:31 Toronto). The accelerated section in `final-implementation-plan.md` maps every original package without changing acceptance. Minutes 0–30: finish 6C backend, repair 6A findings, implement candidate UI, dependency/CI fixes, browser expansion, readiness/body and extraction bounds, local delivery adapter; timebox privacy/trace contracts and independent review. Minutes 30–75: continuously review/integrate; launch contract-approved downstream lifecycle/report/privacy slices from updated HEAD; adapt browser fixtures; do not wait for entire phases. Minutes 75–120: reserve combined formatting/lint/types/tests/build, populated PostgreSQL upgrades, isolated browser/packaging regression and repair time. Targeted checks happen before every merge throughout, not only at the end.

Current bottleneck is agreement/integration of immutable assignment backend and UI, then delivery/privacy interfaces; product/provider decisions gate full accounts and delivery. Safe adapters, bounds and contract preparation do not wait on those choices. Realistic result: more reviewed locally verified implementation plus explicit residual gates. Hosted provider credentials, staging/TLS, actual rollback/restore, manual assistive-technology/user studies and I-O/privacy sign-off cannot be claimed from local mocks or this time target.

### Current dispatched work

All new worktrees below are based on integration `c20b3ed`; names have `AbhiNutakki/` branch prefix. The backend retains its original base and agreed migration. Six new ready sessions plus existing backend were independently inspected via rendered terminal screens at 22:32 UTC: **7/7 displayed `GPT-6-Astra medium fast`**, with actual task commands running; zero unsupported sessions. Earlier four explicit priority confirmations remain historical evidence; completed sessions are released. The next five launches require their own live verification before inclusion in this count.

| Task | Worktree suffix | Dispatch | Exclusive ownership / allocation |
| --- | --- | --- | --- |
| 6C version backend | `iopsych-6c-versions` | `ctx_1d41002f09c5` | Assignments, invitation/report backend, migration 0008; 3110/8110/5550 |
| 6A boundary fixes | `iopsych-6a-boundary-fix` | `ctx_30ec6c9e9a90` | Local session route/tests and API launcher/tests; 3113/8113/5553 |
| 6C candidate UI | `iopsych-6c-candidate-ui` | `ctx_585fc8d50579` | Candidate component, storage, web contract/client/proxy; 3114/8114/5554 |
| Dependency remediation | `iopsych-security-fixes` | `ctx_5ac67cd6ce11` | Root/web/shared manifests and lockfile, runtime floor; 3115/8115/5555 |
| 12A browser expansion | `iopsych-12a-expand` | `ctx_6f6fb5f60c61` | Browser tests/fixtures, isolated runner; 3116/8116/5556, mail 1136/8136 |
| 11B readiness/body bounds | `iopsych-11b-bounds` | `ctx_c990f981efd6` | API main/runtime modules and focused tests; 3117/8117/5557 |
| Security CI/scans | `iopsych-security-ci` | `ctx_e23a7b33b738` | Security workflow/scanner configuration only; 3118/8118/5558 reserved |
| 11B extraction bounds | `iopsych-extraction-bounds` | `ctx_029b02659d84` | Extraction config/provider/service and tests; 3119/8119/5559 |
| 8A local delivery adapter | `iopsych-local-delivery` | `ctx_e371becfa847` | New loopback-only SMTP adapter/tests, no main/issuance edits; 3120/8120/5560, mail 1139/8139 |
| 10A privacy contract | `iopsych-privacy-contract` | `ctx_67da63415309` | Read-only code; lifecycle contract document only; 3121/8121/5561 reserved |
| 9C traceability contract | `iopsych-report-traceability` | `ctx_bc1762186e0b` | Read-only code; trace contract document only; 3122/8122/5562 reserved |
| Integration review | `iopsych-integration-review` | `ctx_5e5821213fd9` | Read-only packaging/storage/isolation review and regression preparation; 3123/8123/5563 |

Fresh setup hooks run concurrently; workers must confirm success before checks. No worker owns another worker's database. Full suites are coordinator-scheduled at integration checkpoints, not run by all workers.

22:33 UTC checkpoint: all **12 dispatched tasks ready/live**, all **12 rendered terminal screens verified `GPT-6-Astra medium fast`**; zero unsupported or setting-interrupted sessions. No coordinator toggle. Schedule commit `3cf79c2` broadcast to all 12 workers; subsequent worktrees start from updated integration HEAD. Readiness/body additive contract approved in `msg_0b1e5267bb0f`: unchanged `/health`, DB-only `/ready`, actual-byte request limit and upload deadline, no schema/hosted certification claim. Current Fast count supersedes the earlier seven-session checkpoint, not its evidence.

Synthetic data and controlled local mail only. No push, public deployment, purchases, real email, production secrets or existing database resets. Preserve ports 3000, 8001 and 8000. Each worker uses a separate checkout and isolated database/schema. No scientific or external approval is inferred from implementation authority.

## First wave

### 22:37 UTC integration checkpoint (supersedes earlier live rows)

Integration HEAD before this record: `9609510`. Completed workers below have reported and been released; no full package acceptance is inferred.

| Slice | Integrated revision | Review / independently executed coordinator evidence | Remaining |
| --- | --- | --- | --- |
| 6A boundary repair | `a0d551b` | 104 launcher tests, 52 route tests, five live Next cases passed; hostile Host never reaches upstream or sets cookie | Combined regression and clean setup evidence reconciliation |
| 6C backend / frontend | `6a8fd01` / `3ee3411` | Backend 53 passed/one PostgreSQL skip in coordinator focused run; frontend 37 passed | Worker reported real PostgreSQL upgrade coverage; independent combined PG run active; retained-content correction and browser integration pending |
| 8A local capture adapter | `806016b` | 47 tests passed/one Mailpit skip; worker actual Mailpit test separately passed | Explicit injection only; lifecycle/provider/outbox still pending |
| Dependency remediation | `7bc15f3` | Independent npm audit reports zero vulnerabilities; reviewed narrow manifest/lock changes | Combined build/browser/container checks active |
| Security CI | `360c5dc` | Four scanner regression tests passed; independent fail-closed jobs reviewed | Worker zero Python/history/source findings; integrated-revision/hosted checks pending |
| 11B extraction bounds | `3078d9e` | 65 focused tests passed | Hard cancellation, distributed admission, hosted/provider gates remain |
| 11B readiness/upload bounds | `91bd92f` | 17 focused tests passed, one deprecation warning | DB deadlines/schema readiness and hosted validation remain |
| 12B profile contrast | `9609510` | Two class changes reviewed; worker computed contrast 7.56:1, component tests passed | Actual browser axe rerun active, no manual acceptance |
| Trace/privacy contract preparation | `66bde97` / `f662043` | Reviewed exact additive trace envelope and privacy locking proposal | Engineering slices dispatched; interpretation/privacy policy approvals remain pending |
| Independent integration review | `4c7caf3` | Two reproduced recovery defects accepted | Decline cleanup integrated; clear-at-review reset still being fixed |

New downstream worktrees start at `4c7caf3` (integrity/profile fixes started at `360c5dc`). Their seven new rendered sessions plus two correction sessions all display Fast; no unsupported sessions. Browser worker remains Fast. At dispatch checkpoint ten sessions were live; profile worker has since completed/released, leaving nine useful tasks. Memory free 32%; hold further heavy builds until current builds settle, rather than spawn duplicate regressions.

| Active task | Dispatch | Ownership / runtime |
| --- | --- | --- |
| 6C retained-content integrity | `ctx_929fe435c930` | Registry and focused tests only; 3124/8124/5564 |
| 12A production browser expansion/rerun | `ctx_6f6fb5f60c61` | Browser fixtures/runner/tests; 3116/8116/5556, mail 1136/8136 |
| 9C historical trace backend | `ctx_055f6c35334f` | Report trace module/schema/route/service, canonical fixtures; 3126/8126/5566 |
| 9C historical trace frontend | `ctx_22fa434f26b8` | Trace parser/client, internal GET proxy, report drawer; 3127/8127/5567 |
| 10A export/anonymization serialization | `ctx_b2a989cc4f5f` | Privacy service and new PostgreSQL interleaving tests; 3128/8128/5568 |
| 9A recovery correction | `ctx_d12515fe37f3` | Candidate component/tests only; 3129/8129/5569 |
| 7A production sign-out correction | `ctx_a4744da9078a` | Session route/tests and cookie helper if required; 3130/8130 |
| Combined regression | `ctx_38a566c6a71b` | Read-only application, one broad check/build/PG run at frozen revision; 3131/8131/5571 |
| Updated packaging verification | `ctx_04786040c8c9` | Read-only deployment/application, new isolated container project; 3132/8132/5572 |

9C engineering contract is approved exactly as proposed in the trace document; backend owns language-neutral fixtures and sends them to UI before final integration. Existing report responses remain unchanged; no new interpretation is approved. Privacy slice preserves existing export/deletion policy and schema, adding serialization only. Browser found a real production sign-out failure (204 followed by authenticated 200); dedicated correction is active, not waived. Combined regression and packaging checks are delegated independently while coordinator remains sole integrator. User decisions requested for provider defaults and product scope are unanswered at this checkpoint.

All three child worktrees started at committed integration revision `a8de73c`. Branches have prefix `AbhiNutakki/`; worktrees are under `/Users/abhiramnutakki/orca/workspaces/iopsych/`.

| Package/task | Branch | Task / active dispatch | Ownership | Ports / DB | State / evidence |
| --- | --- | --- | --- | --- | --- |
| 6A | `iopsych-6a-setup` | `task_51aea6c0d21e` / `ctx_454cacc97083` | Setup/startup, local synthetic login, focused tests, README, 6A report | 3101 / 8101 / `iopsych_6a`, DB port 5541 | Integrated `486c6b2`; worker released; acceptance reopened by review |
| 6B preparation | `iopsych-6b-decisions` | `task_3b6a7f8f3efd` / `ctx_d7fff07517b3` | `6b-decisions.md`, `6b-report.md` only | 3102 / 8102 / `iopsych_6b` reserved | Integrated `4638236`; worker released; actual decisions pending |
| 12A/12B audit | `iopsych-12ab-audit` | `task_7d18dbac142d` / `ctx_03a733782cc2` | Read-only code/test audit; `12ab-audit.md` report only | 3103 / 8103 / `iopsych_audit` reserved | Integrated `8bb1016`; worker released; audit is not acceptance |

Initial dispatches `ctx_8f1ba11ba1d4`, `ctx_30f32ea5ece7`, `ctx_c6e202ebf48d` failed before task delivery because of Codex's update prompt. Selected “Skip until next version” and retried the same tasks in the same terminals using supported `--retry-of`; no duplicate editors. Those retry turns started but the provider rejected the literal `gpt-6` model for the ChatGPT account. All three were explicitly stopped after inspecting the terminal error. The worker model menu lists GPT-6-Astra as available/default; subsequent starts use `gpt-6-astra`, with actual agent tool execution observed. Audit retry `ctx_e879905cb46c` failed before delivery with `terminal_handle_stale`, then its owned terminal was released through Orca and the same task retried. No task implementation occurred in rejected-model turns. Saved setup: `npm ci && PYTHON_BIN=python3.12 npm run api:install`.

## Package ledger

Historical expanded wave confirmed eight active workers, all with `turn_started` and requested/effective `gpt-6-astra`. These bounded slices below are now integrated and their workers released; the current dispatched-work table above governs active ownership. Four worktrees branched from `3602cb0`; runner branched from `8450a09`. Branch names below have `AbhiNutakki/` prefix.

| Slice | Branch | Task / dispatch | Exclusive ownership | Runtime allocation |
| --- | --- | --- | --- | --- |
| 12A early runner | `iopsych-12a-runner` | `task_39bfc496bb85` / `ctx_1102016053c8` | `tests/browser/**`, `scripts/browser-e2e*`, `12a-scaffold.md` | 3104/8104/5544, local mail 1124/8124 |
| 9A compatible storage fixes | `iopsych-9a-storage` | `task_23dde4095af6` / `ctx_75b5d5c7e879` | candidate-storage helper/tests, candidate-assessment component/tests, `9a-report.md` | 3105/8105/5545, `iopsych_9a` |
| 11A packaging preparation | `iopsych-11a-packaging` | `task_1147cce72e78` / `ctx_4d2b01907bbf` | `deploy/**`, app Dockerfiles, `.dockerignore`, `11a-report.md` | 3106/8106/5546, `iopsych_11a` |
| 12B preparation | `iopsych-12b-a11y` | `task_e6bd8f0e591f` / `ctx_2e6f574be424` | `docs/accessibility/**`, `12b-preparation.md`; no app edits | 3107/8107/5547, `iopsych_a11y` |
| 12C preparation | `iopsych-12c-runbooks` | `task_04ff3171b77a` / `ctx_dbef9130a02e` | `docs/operations/**`, `12c-preparation.md` only | 3108/8108/5548, `iopsych_runbooks` |

All report basenames above live under `docs/implementation/`. Setup hooks succeeded for the completed slices. Root package/lock ownership has transferred to dependency remediation; runner retains an isolated test-tool manifest/lock. Automated axe tooling belongs to the active browser worker. Full package acceptance remains pending despite these preparations being integrated.

Pending means no acceptance claimed. A prepared decision or scaffold never closes the full package. Revision-linked reports will record exact commands, results, failures/skips and external limitations.

| Package | Dependencies | Owner / status | Acceptance evidence required | Branch / commit / blockers |
| --- | --- | --- | --- | --- |
| 6A setup | Existing foundation | Implementation integrated; review blockers; fixes active | Fresh setup, PostgreSQL migration/seed/tenant verification, actual launcher regression, synthetic login | `486c6b2`; review `c20b3ed`: actual Host bypass and Boolean guard mismatch; full acceptance pending fixes/recheck |
| 6B decisions | None | Preparation reviewed/integrated; user/product/I-O decide | Every decision has owner, four structure examples, approved choices and spec reconciliation | Worker `298ce31` → integration `4638236`; actual decisions pending |
| 6C historical versions | 6B for full acceptance | Backend and frontend active; contract agreed | Populated upgrades preserve invites/drafts/submissions/v1 reports; assignment policy | Backend reports 53 focused tests incl. PostgreSQL; not independently verified yet; decision gate remains |
| 7A provider/session | 6A, identity choice | Unassigned; gated | Separate identities, callback/claims/expiry/sign-out/redirect negatives | Provider decision/configuration |
| 7B provisioning | 7A, membership choice | Unassigned; gated | Audited grant/change/revoke, deactivation and tenant tests | Dependencies |
| 7C manager workflow | 6B, 7A | Unassigned; gated | Browser handoff/edit/reject/approve, immutable versions, archive permissions | Decisions/dependencies |
| 8A delivery lifecycle | 6C, delivery choice | Local adapter slice dispatched; lifecycle gated | Local captured delivery, idempotency, uncertainty/commit recovery, secure credentials | Delivery decision, durable recovery contract and staging pending |
| 8B invitation UI | 8A, 7C | Unassigned; gated | Browser approval-to-invitation, status/permission/error coverage | Dependencies |
| 9A device recovery | 6C for full acceptance | Storage fixes integrated; pinned UI integration active | Denied/quota storage, truthful saving, incomplete edits, expiry, minimal receipts | `f63ae17`, report `4e1b3ae`; independent 17 tests pass; full acceptance pending integration/browser |
| 9B progress/context | 6B, 6C, 9A | Unassigned; gated | Approved promise, persistence/access/version/privacy coverage | Scope decisions |
| 9C evidence/matching | 6B, 6C | Trace contract preparation dispatched; semantic changes gated | Approved four structure extremes, language parity, item-level traces, historical readers | Actual interpretation approval; preserve v1 inverse semantics |
| 10A privacy lifecycle | 6B, 6C, 8A, 9B | Lifecycle inventory/contract dispatched | All lifecycle categories, policy snapshots, rights and PostgreSQL races | Privacy decisions/dependencies; no policy approval inferred |
| 10B privacy admin | 10A, 7B | Unassigned; gated | Bounded discovery, related audit, downloads and rights workflow | Dependencies/verified contacts |
| 10C retention | 10A, 11A scheduler | Unassigned; gated | Backlog drain, missed-run alerts, restore deletion replay | Policy/scheduler/restore |
| 11A packaging | Hosting choice; integrate 6A | Packaging integrated; independent review active | Reproducible assets/schema, controlled migrations, graceful shutdown, rollback rehearsal | `bb5d1fd`, report `b4c1056`; worker local container smoke only; hosting/rollback pending |
| 11B runtime bounds | 6A, 7A, 8A; staging 11A | Disjoint readiness/body and extraction slices dispatched | Hosted validation, readiness, size/time/concurrency limits, synthetic provider smoke | Full hosted/provider gates pending |
| 11C operations | 11A; integration 8A/11B | Unassigned; gated | Safe correlation/logs/alerts, encrypted backup/restore objectives and rehearsal | Hosting/responders/provider setup |
| 12A E2E | Features 7–10, 11A/11B; scaffold early | Runner integrated; expansion/security/review active | Production browser/PostgreSQL journey and negatives, zero required skips, hosted evidence | Runner `de9fc5e`, report `a8a37a3`; independent 13 safety tests pass; full journey/hosted pending |
| 12B accessibility | Completed screens, 12A; incremental audit early | Preparation integrated; automated coverage expansion active | Automated scans plus keyboard/screen-reader/device checks and measured user studies | `637e034`; manual/user evidence pending; axe owned by runner |
| 12C runbooks/rehearsal | 10C, 11A–C, 12A/B | Runbook preparation integrated; rehearsal pending | Revision-linked rehearsal, named owners and actual content/privacy sign-off | `f9cfaa5`; external reviews, named owners and actual rehearsal pending |
| 12D demo/handoff | 12A–C technical gates | Unassigned; gated | Controlled synthetic demo, walkthrough, evidence, contribution/license/limitations | Public publication separately authorized |

## Integration evidence

6B documentation commit `298ce31` reviewed, independently passed Prettier and diff checks, integrated as `4638236`. Coverage audit `ed41304` reviewed, independently passed Prettier and diff checks, integrated as `8bb1016`. Both completed workers reported success for their bounded tasks and were released; neither closes full package acceptance. Audit worker reports 104 web tests passing and 127 API tests passing/two PostgreSQL skips under explicitly reduced coverage/cache settings; see report, not a release gate. Existing historical test counts remain baseline context only.

6C backend compatibility task `task_d7602200cf01`, dispatch `ctx_1d41002f09c5`, branch `AbhiNutakki/iopsych-6c-versions` started from `4638236`, with 3110/8110/5550 and `iopsych_6c` reserved. Contract and migration 0008 were agreed before edits; frontend is now separately dispatched. Coordinator review requested exact retained-content recognition even when a tampered payload has a recomputed checksum. No scoring change or approval is implied. User questions for provider defaults and journey scope remain pending asynchronously; interpretation remains reviewer-gated.

Independent coordinator checks so far: local-login/sign-in Vitest 25 passed; storage/component Vitest 17 passed; launcher/API-login pytest 14 passed with one warning; browser-runner safety pytest 13 passed; deployment Compose configuration validation passed. These are targeted checks, not a combined release regression. Security assessment is integrated as `d2d46cd`; remediation and fresh scans are active. No full package is newly declared accepted by this ledger refresh.

## Shared contract decisions

- 6A additive local contract approved by coordinator in `msg_3e7b0f122730`: fixed synthetic identity selector at `POST /v1/auth/local-login`, short-lived credential exchanged server-side by `POST /api/session/local` into the existing HttpOnly cookie. Default disabled, explicit development policy, loopback peer/host/configured origins, same-origin mutation checks and exact seeded identity/tenant checks required. No provider/scientific decision, migration or shared-package schema change authorized by this approval.
- Docker is available (server 29.8.0); existing `iopsych-postgres-1` on 5432 stays intact. 6A has a separate Compose project/database port 5541 allocation.
