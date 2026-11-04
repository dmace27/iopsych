# 12C bounded preparation handoff

Date: 2026-11-04. Baseline: committed integration `3602cb0`. Scope:
documentation only in `docs/operations/**` and this report. Package 12C/original
5C is **not complete**; no synthetic staging rehearsal or actual approval is
claimed.

## Delivered

[Operations index](../operations/index.md) links actionable deployment/rollback,
incident/key rotation, support/accommodation, privacy
export/deletion/correction/withdrawal, training, retention, backup/restore
deletion replay and synthetic rehearsal procedures. The rehearsal matrix maps
the section-16 launch checklist to current capabilities, required evidence and
package blockers. Roles are explicitly owner-unassigned; stop/restart criteria
separate technical readiness from actual pilot authorization.

Inspected the required plans/spec/progress and current scripts, API
routes/services/settings, session behavior and environment templates. No
applicable ancestor/root/docs AGENTS.md was found; the only repository AGENTS.md
is scoped to apps/web and no web files were changed. Confirmed baseline facts:
unconfigured delivery, liveness-only `/health`, single auth/invite verification
keys, assessment-ID privacy operations, submitted-only one-batch retention and
no implemented restore deletion replay.

Coordinator confirmed via Orca message `msg_80ba400333bb`: use
`deploy/README.md` as the 11A handoff boundary and
`docs/implementation/11a-report.md` for limitations, with commands pending until
the 11A commit is reviewed. No shared contract, migration, dependency or policy
changes were proposed or made.

## Verification and actual commands

- `git rev-parse --short HEAD`: `3602cb0` before edits; `git status --short`:
  initially clean.
- `rg --files` and targeted `cat`, `sed`, `rg` inspection: confirmed documented
  routes, settings and root npm scripts against source. Exploratory lookup of
  root `.env.example` and `apps/web/src` found neither; corrected inspection to
  `apps/api/.env.example`, `apps/web/.env.example` and `apps/web/app`/`lib`.
  These were read-only path misses.
- Local Markdown formatting, link/command-reference validation and whitespace
  results: recorded below after execution.
- No runtime tests, database commands, build, installation, migration, seed,
  retention mutation, mail, provider calls, deployment, restore or rollback were
  executed. Documentation-only checks avoid duplicating 12A/6A validation or
  racing setup. No full suite was run.

## Assumptions, blockers and remaining gates

Baseline behavior is pinned to `3602cb0`; future feature integration must update
procedures and run the matrix at the actual release revision. API existence is
not browser/provider/operational acceptance. Reserved ports/database were
unused. Existing npm commands are inventory, not authorization to operate a
hosted environment.

Remaining gates: 6A setup integration; actual 6B decisions/review and 6C version
compatibility; 7A–C identities/provisioning/review; 8A/B delivery/recovery/UI;
9A–C truthful persistence, approved scope and report evidence; 10A/B complete
rights/lifecycle; 10C scheduler/backlog/deletion replay; reviewed 11A packaging
and commands; 11B readiness/configuration/bounds; 11C safe telemetry,
responders, encrypted backup and measured recovery; 12A
browser/PostgreSQL/HTTPS/hosted evidence; 12B accessibility and measured
usability; then full 12C rehearsal, named owners, working contacts, training and
actual revision-linked I-O/privacy/product signoffs. 12D publication remains a
later authorized action. No real-participant approval, policy, contacts, RTO/RPO
or scientific interpretation was invented.

Commit identification: the documentation delivery commit is the commit adding
this report (resolve with
`git log -1 --format=%H -- docs/implementation/12c-preparation.md`); its exact
SHA is sent in the Orca completion message to avoid a self-referential commit
hash.
