# 9A candidate recovery follow-up

Base: `4c7caf3`, including the merged 6C UI `3ee3411`. Dedicated worktree:
`iopsych-candidate-recovery`. Scope is the candidate component, its tests, and
this report only. Read web AGENTS, the installed Next client directive guide,
the accelerated implementation schedule, progress ledger, 6C UI handoff, 9A
storage handoff, and integration review.

## Changes and reproduced findings

Clearing device data from review now resets the block index to zero, removes
validation/action errors, resets save status, and clears choices before pausing.
Continuing removes the stale device message and focuses the first block heading
through the existing focus effect. The regression completes all six blocks,
causes a submission error, clears from review, resumes at block one, verifies
empty choices and absent stale error/review text, and completes the journey
again. An unanswered first block still prevents forward navigation.

The immediate-decline cleanup in `3ee3411` already works. A new regression seeds
a historical answer-bearing draft before opening the consent page and a receipt
before declining, then verifies both keys disappear immediately after the
acknowledged decline without a reload or definition fetch. No replacement
storage or API behavior was needed.

Token changes previously left the old assignment/questions visible during the
next invitation fetch. A late consent acknowledgement or consent-triggered
definition response also overwrote the new invitation screen. New deferred
promise tests reproduced all three paths. The exported component now keys its
stateful child by token, resetting assignment, choices, position, errors and
pending flags together. An unmount guard ignores late consent/definition and
submission responses before their follow-up state/storage work. A submission
already sent may still succeed on the server; reopening that invitation retains
the existing server-authoritative completion check. Requests are not cancelled.

The late-submission regression verifies that an old receipt cannot replace the
new invitation, create device receipts after navigation, or disable choices in
the new journey. The existing initial-fetch effect already has an active guard.
No schema, storage helper, API, dependency, migration or inline-comment edits
were made.

## Exact validation

Initial component run with the new recovery/token/decline tests and unchanged
implementation: **15 passed, 5 failed**. Four failures demonstrated the reset,
stale assignment, pending consent, and pending definition defects; the immediate
decline regression passed. The fifth was an existing keyboard-focus timing race
in the incomplete-block test, fixed by awaiting initial heading focus before
moving focus to Continue (matching the existing consent/resume test pattern).
After the implementation fix the component run passed **20/20**; the final
late-submission test increased that count to **21**.

Final checks from `apps/web`:

```sh
npx vitest run --coverage.enabled=false lib/candidate-storage.test.ts 'app/candidate/invites/[token]/candidate-assessment.test.tsx'
npx eslint 'app/candidate/invites/[token]/candidate-assessment.tsx' 'app/candidate/invites/[token]/candidate-assessment.test.tsx' --max-warnings=0
```

Vitest: **29 passed across 2 files, zero failures/skips**, exit 0 (21 component,
8 storage). ESLint: exit 0. Coverage was explicitly disabled for this focused
run; this is not a full coverage gate.

From the repository root:

```sh
npm run typecheck --workspace @iopsych/web
npx prettier --check 'apps/web/app/candidate/invites/[token]/candidate-assessment.tsx' 'apps/web/app/candidate/invites/[token]/candidate-assessment.test.tsx' docs/implementation/9a-recovery-fix.md
git diff --check
```

All passed, exit 0. Typecheck ran Next route generation and TypeScript; its
incidental `next-env.d.ts` path change was restored to preserve ownership.

## Remaining gates

Browser-owner integration rerun remains required; these are synthetic jsdom
regressions with mocked API responses. No server, database, browser build,
external email, deployment, push, purchase, secrets access or database reset was
performed. Reserved 3129/8129/5569 and protected 3000/8000/8001 were unused.
Coordinator owns integration and combined acceptance. This bounded fix does not
close full 9A, accessibility, release, scientific, product or privacy
acceptance.
