# Integrated trace, discovery, telemetry and session review

Reviewed 2026-11-04 at `e6a39f4d0c92776b7e188a62fc63a734b2e38a51` in the
assigned `iopsych-latest-review` child worktree. Scope was the application
changes after `f5bd781`: retained report trace backend/UI, request telemetry,
invitation discovery, session navigation, and their existing privacy/audit
boundaries. Read `final-implementation-plan.md`, `mvp-spec.md`, `finish.md`, and
the applicable `apps/web/AGENTS.md` instructions.

## Findings

**No actionable correctness or security regression was confirmed in the scoped
changes.** Consequently there are no new severity/file/line/reproduction entries
to escalate. This is a bounded code review with targeted automated checks, not
release approval or a claim that the remaining product packages are complete.

The following boundaries were inspected and exercised by the targeted tests:

| Boundary                                  | Code anchor                                                                                | Evidence and conclusion                                                                                                                                                                                                                                                                                                                       |
| ----------------------------------------- | ------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Trace authorization and deletion ordering | `apps/api/app/reports/service.py:188`                                                      | Assessment ownership and report ownership are checked separately; the assessment lock precedes the report lock, retained ORM state is refreshed, and anonymization/linkage checks precede the trace builder. Existing audit middleware holds the transaction through the required audit commit. No alternate unlocked trace return was found. |
| Historical evidence consistency           | `apps/api/app/reports/trace.py:30`                                                         | Exact retained definition/hash, assignment, rescored responses, saved scores, report summaries and question IDs are checked. Missing/tampered/unknown inputs fail closed; historical report prose is not rematched or overwritten. Complete, skipped, all-skipped and threshold-boundary cases pass.                                          |
| Trace browser integration                 | `apps/web/lib/report-trace-contracts.ts:160`, `apps/web/app/reports/report-detail.tsx:367` | The proxy permits the additive GET route; parsing binds evidence to the report and verifies block choices, totals, thresholds and completeness. Drawer request cleanup, report changes, retry and authorization/unavailability states pass targeted component/client tests.                                                                   |
| Invitation discovery                      | `apps/api/app/invitations/discovery.py:60`                                                 | Role, result and cursor-anchor queries remain tenant scoped; cursor decoding is shape bounded and canonicalized against the stored anchor. Timestamp/UUID keyset ordering, concurrent newer inserts, permission denial, audit failure and safe response fields pass. An unsigned cursor supplies a position, not authorization.               |
| Telemetry                                 | `apps/api/app/runtime/telemetry.py:37`                                                     | Route labels come from registered templates, request IDs are generated server-side, and emitted fields exclude request bodies, credentials and identity. Actual candidate-route redaction, early failures, exception correlation, cancellation and bounds pass.                                                                               |
| Session navigation                        | `apps/web/app/ui/site-header.tsx:98`, `apps/web/lib/safe-return-to.ts:2`                   | Current identity comes from the authenticated endpoint; stale requests are invalidated, sign-out failure remains visible, candidate pages omit account fetching, and return paths are restricted to actual internal page shapes. No open redirect or candidate-token propagation was found.                                                   |

## Fresh verification

From the repository root:

```sh
.venv/bin/python -m pytest -c apps/api/pyproject.toml \
  apps/api/tests/test_report_trace.py \
  apps/api/tests/test_invitation_discovery.py \
  apps/api/tests/test_telemetry.py --no-cov -q -k 'not postgres'
```

Result: **92 passed, 1 deselected in 5.41 seconds**. The deselected case is
`test_postgres_trace_and_deletion_serialize_in_both_orders`. One existing
Starlette/httpx TestClient deprecation warning was emitted. These are synthetic
in-process and isolated SQLite tests; they do not establish PostgreSQL locking.

From `apps/web`:

```sh
../../node_modules/.bin/vitest run \
  app/reports/report-detail.test.tsx \
  lib/report-trace-client.test.ts \
  app/ui/site-header.test.tsx \
  lib/safe-return-to.test.ts \
  app/sign-in/page.test.tsx \
  app/sign-in/sign-in-form.test.tsx \
  'app/api/internal/[...path]/route.test.ts'
```

Result: **7 test files passed, 116 tests passed in 1.61 seconds**. These are
component/client/proxy tests, not a production-browser rehearsal.

Total fresh targeted checks: **208 passed**, no failures. No full suite,
dependency installation, application edits, migration, database reset, external
provider call, email, push or deployment was performed. No server was started;
allocated ports 3142/8162/5582 and protected ports 3000/8001/8000/5432 were
untouched. Only this review document is changed.

## Limits and remaining work

- The PostgreSQL race test was inspected, including both lock orders and its
  `pg_blocking_pids` assertion. Earlier execution evidence is in
  `report9c-trace-backend.md`, tied to that worker's revision. It was not rerun
  here and is not represented as fresh integrated-revision evidence.
- Invitation discovery is intentionally a backend slice. The browser proxy/UI
  still needs invitation management integration; stored invitation status does
  not synthesize expiry or submission state. These are documented remaining
  acceptance items, not newly introduced regressions.
- Session polling does not replace provider login, and API completion telemetry
  does not certify ingress/web/provider logging or hosted alerting. Existing
  synchronous database work in async middleware/routes remains an operations
  concern already recorded in `finish.md`; no load-test claim is made here.
- Coordinator-owned integrated PostgreSQL/browser and release checks remain
  necessary. Scientific interpretation, product scope, privacy policy and
  real-participant approvals remain unchanged and outstanding where previously
  gated. This review grants none of them.
