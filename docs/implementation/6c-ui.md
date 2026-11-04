# 6C candidate UI compatibility slice

Implemented in the isolated `iopsych-6c-candidate-ui` worktree against the
read-only backend handoff
`iopsych-6c-versions/docs/implementation/6c-contract.md`. This is bounded
frontend engineering evidence, not full 6C acceptance or scientific, product,
provider, or real-pilot approval.

## Changes

- Added strict assigned-definition envelope validation and the same-origin GET
  definition client/proxy route; landing, consent, and submit wire shapes remain
  unchanged. The client checks ID/version/scoring agreement, explicitly
  recognizes the retained v1 reader, and verifies the SHA-256 of sorted compact
  UTF-8 JSON.
- Questions are fetched/rendered only after affirmative server consent. Failed,
  unknown, malformed, or mismatched assignments show the existing retry/recovery
  screen without a current-definition import fallback. Submitted invitations
  keep their server-authoritative completion flow without needing definition
  content.
- New device drafts carry `definition_sha256` plus the existing response
  ID/version. Load/save requires the assigned definition and validates
  block/item membership. Different hashes/IDs/versions are rejected and
  incompatible device drafts are removed. Hashless historical drafts are
  accepted only for the frozen v1 ID, version, and checksum
  `021233ca4dab9c86b87aeabca88f503bf7c70fd0b0d324c64e788b620aeb6e3c`; the next
  successful save upgrades their envelope. Unknown history is not guessed.
- Existing 9A expiry, truthful save status, storage denial/quota handling,
  partial choice cleanup, clear-device/save-exit controls, and minimal
  answer-free receipts remain intact. No backend, shared package, dependencies,
  migration, or progress ledger was edited.

## Commands and results

Setup artifacts from the saved
`npm ci && PYTHON_BIN=python3.12 npm run api:install` setup were verified using
`npm ls --depth=0` (exit 0, installed workspace dependency resolution),
`.venv/bin/python --version` (Python 3.12.16), and
`.venv/bin/python -m pip check` (exit 0, no broken requirements). No server,
database, or port was started or reset; reserved 3114/8114/5554 and existing
3000/8000/8001 remain untouched.

From the repository root:

```sh
npm run typecheck --workspace @iopsych/web
```

Passed. Next's generated `next-env.d.ts` path churn was restored before
committing. An initial typecheck caught an accidental asynchronous retry-handler
edit, which was fixed before the passing run.

From `apps/web`:

```sh
npx vitest run --coverage.enabled=false lib/candidate-api.test.ts lib/candidate-storage.test.ts 'app/candidate/invites/[token]/candidate-assessment.test.tsx' 'app/api/candidate/invites/[...path]/route.test.ts'
npx eslint lib/candidate-api.ts lib/candidate-api.test.ts lib/candidate-contracts.ts lib/candidate-storage.ts lib/candidate-storage.test.ts 'app/candidate/invites/[token]/candidate-assessment.tsx' 'app/candidate/invites/[token]/candidate-assessment.test.tsx' 'app/api/candidate/invites/[...path]/route.ts' 'app/api/candidate/invites/[...path]/route.test.ts' --max-warnings=0
```

Final focused run: **37 tests passed across four files**, no skips; targeted
ESLint passed. Coverage collection was deliberately disabled for this focused
slice, not represented as a full coverage gate. One intermediate combined run
exposed a keyboard-focus timing race in the existing resume test; its explicit
heading-focus wait now precedes keyboard navigation. The test passed in
isolation and in the final combined run. Prettier and `git diff --check` also
passed.

Tests cover consent/decline fetch gates, definition failures both on open and
after consent, retry, pinned content instead of bundled text, unknown
IDs/versions, scoring/matching versions, metadata mismatch and hash mismatch,
frozen hashless v1 resume/upgrade, new-hash binding, foreign block/item
rejection, expiry, denied storage, quota, keyboard completion, and answer-free
receipts.

## Remaining integration work

Backend endpoint/migration 0008 and populated historical upgrade acceptance
remain backend/coordinator-owned. Run the combined browser/API/PostgreSQL
acceptance once that backend revision is integrated; this work used mocked
focused API/UI tests. Future semantic versions require explicit frontend reader
registration rather than changing the retained v1 interpretation. Browser
integrity verification uses Web Crypto (HTTPS or localhost); integrity is not a
signature or content approval. No external email/provider calls, deployment,
purchases, or pushes occurred.
