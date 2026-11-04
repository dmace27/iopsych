# Privacy discovery lifecycle reconciliation (DR-01)

Implemented 2026-11-04 in `AbhiNutakki/iopsych-privacy-refresh` for
`docs/implementation/discovery-review.md` finding DR-01. Scope is the privacy
workspace, its component tests, and this report. Read the applicable web AGENTS
instructions, installed Next.js `use client` documentation, and the final
implementation plan before changing the client component.

## Result

Successful anonymization records the authoritative assessment ID and timestamp
from its response. Successful retention records every returned assessment ID,
including other rows on the current discovery page. Discovery rendering combines
these confirmations with lookup data, so a later stale response cannot change a
known anonymized assessment back to `Anonymized: No`. Confirmations last for the
mounted workspace only and are never written to browser storage. Retention does
not return per-assessment anonymization timestamps; its confirmation reads
`Yes (confirmed by retention)` rather than treating the run completion time as
an assessment timestamp. Existing deletion confirmations retain their exact
dates.

Post-mutation status/audit refresh keeps the workspace and success
acknowledgement visible. A failed refresh explicitly reports that the operation
completed but status and audit history could not be refreshed; it does not imply
the mutation failed. A denied administrator recheck still switches to the
access-denied view. The existing working/loading locks prevent discovery changes
during mutation or refresh and prevent mutations during lookup. Selection stays
intact. Successful deletion clears export and confirmation; retention does the
same when its result includes the selected assessment, while preserving
unaffected selection artifacts. Failed mutations never establish anonymization
confirmations.

## Focused verification

- `cd apps/web && npx vitest run app/privacy/privacy-workspace.test.tsx`: **18
  passed**, including the original eight tests and ten new cases covering
  deletion reconciliation, selected and other-row retention, unaffected rows,
  artifact cleanup, both mutation failure paths, both status-refresh failure
  paths, delayed stale lookups after both operations, and discovery locks during
  a pending mutation and delayed status refresh.
- `cd apps/web && npx eslint app/privacy/privacy-workspace.tsx app/privacy/privacy-workspace.test.tsx --max-warnings=0`:
  passed.
- Prettier applied to the two owned TypeScript files; `git diff --check`:
  passed.

All cases use synthetic mocked API responses in jsdom. No backend, policy,
contract, migration, database, ports, browser runtime, mail, secrets,
deployment, purchase, or push operations were involved. No full-suite, full
typecheck, coverage-gate, or native-browser result is claimed. The coordinator
can integrate this focused commit and include it in its owned browser acceptance
run; this change does not close unrelated discovery review findings or release
gates.
