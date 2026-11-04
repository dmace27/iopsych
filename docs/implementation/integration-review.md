# Integrated packaging, runner, and storage review

Reviewed 2026-11-04 at `c20b3eddc21f73870a87fb27503151da43be8048` in the
dedicated `AbhiNutakki/iopsych-integration-review` worktree. Scope: integrated
11A `bb5d1fd`, 12A `de9fc5e`, and 9A `f63ae17`, their tests and handoffs. Read
the implementation plan, MVP specification, finish review, progress ledger and
web AGENTS. This report is the only repository edit. No service, database,
browser build, deployment, dependency install, or full suite was run.

## Findings requiring follow-up

### R1 — P2: clearing answers does not reset the assessment position

`apps/web/app/candidate/invites/[token]/candidate-assessment.tsx:478` clears
choices but leaves `currentBlockIndex` unchanged; line 529 resumes at that
index. Reproduced using the actual component in jsdom: skip all six blocks,
enter review, choose **Clear device data**, then **Continue assessment**. The
screen shows **Block 6 of 6**, with all choices erased and progress at 100%,
instead of the first unanswered block. The existing clear-device test stops at
the paused screen and misses this continuation.

Following that state through the code, completing block six permits review
again: `goForward` checks only the current block, and line 714 unconditionally
claims all six are ready. Submission's count guard prevents an incomplete server
write, so this is a recovery/UX defect rather than demonstrated backend
corruption. Reset the block index on clearing and cover clear-from-review →
continue → complete; ideally review labels derive from actual completeness.
Treat this as a 9A acceptance blocker, not a reason to discard the bounded
storage improvements already integrated.

### R2 — P2: immediate decline omits terminal device cleanup

`candidate-assessment.tsx:279` accepts the server decline and switches views
without clearing device state. Cleanup exists on initial fetch at lines 172–173,
so reload fixes the discrepancy, but the declined screen tells the candidate
they can close the window and offers no clear-device control.

Reproduced with a valid-shaped local draft under
`iopsych.candidate.v1.<invitation_id>.draft`, an initial unconsented invite, and
a successful decline response: the key remains immediately after the declined
heading appears. This is a stale/legacy/device-state edge case; this review did
not demonstrate that a new unconsented journey naturally creates such a draft.
The fixture used an empty response array, sufficient to demonstrate omitted
removal; the branch does not inspect or remove an answer-bearing draft either.
Clear both keys after acknowledged decline and surface cleanup failure honestly.
The storage helper already provides the needed best-effort behavior. Add a
component regression for pre-existing draft and legacy completion data.

Both findings were sent to the coordinator in `msg_9faba9c657b8`. No source fix
was made here; coordinate with the 6C candidate UI owner to avoid competing
changes in the same component.

## Packaging and runner conclusions

No additional confirmed merge blocker was found in the scoped container or
runner changes. This is a bounded static/test review, not runtime certification.

- API image includes shared Python source, definitions, schemas and migrations;
  its editable install path matches the runtime copy. Both images use non-root
  users and direct production commands. Compose separates explicit migration
  execution from service startup and does not seed automatically.
- Container health checks establish liveness only. The documented prior smoke
  used older source and seven migrations; it cannot establish correctness after
  6C, dependency remediation, or the forthcoming readiness changes. Existing
  restart evidence is not a populated upgrade, previous-image rollback or active
  request drain test. These limitations are accurately recorded in 11A's report.
- Runner refuses inherited target/credential settings and dotenv files, checks a
  Unix-socket Docker context and occupied ports, generates a fresh project, and
  registers cleanup before startup. Normal process cleanup is limited to its own
  process groups and Compose project. SIGKILL and races after port preflight
  remain outside this guarantee; the runner is not a network sandbox.
- `scripts/browser-e2e.py:157` directly creates an `AssessmentInvite` without
  explicit assignment versions. After 6C, verify the fixture is assigned the
  intended immutable version, either by explicit fields or a reviewed default.
  `tests/browser/smoke.spec.ts:5` loads v1 from disk; it does not prove that the
  browser receives and restores an assigned historical definition. These are
  concrete integration seams, not a claimed failure against unlanded code.
- The 13 safety tests mock refusal paths and validate adapters. They do not
  execute normal cleanup, interrupt cleanup, failed-start cleanup, process-group
  ownership, or token redaction. Add cheap mocked lifecycle coverage when the
  runner is next changed; retain owner-run real cleanup evidence separately.
- The three committed browser tests cover health/internal denial, invalid
  credentials, and consent/decline. They do not exercise successful login,
  candidate completion/reload/storage denial, assignment upgrades, report or
  privacy journeys. Seeded SMTP delivery is not browser invite issuance.
- Dependency assessment and 6A boundary review remain with their existing
  owners; this review neither duplicates nor supersedes those findings.

## Evidence actually executed

From the reviewed revision:

```sh
(cd apps/web && ../../node_modules/.bin/vitest run \
  lib/candidate-storage.test.ts \
  'app/candidate/invites/[token]/candidate-assessment.test.tsx')
.venv/bin/python -m pytest -q -o addopts='' tests/browser/test_scaffold.py
docker compose -f deploy/compose.yaml config --quiet
docker compose -f tests/browser/compose.yaml config --quiet
```

Results: **17 web tests passed, 13 runner tests passed, zero skips in these
committed test selections; both Compose configurations validated**. Coverage
thresholds were not run; these were focused checks, not full-suite acceptance.

Two extra tests were appended to a temporary copy of the component test outside
the repository, preserving its API mocks and setup/cleanup. A temporary Vitest
config enabled automatic JSX and jsdom; imports referenced this worktree.
Running `vitest run --config <temporary-config> -t 'review probe'` failed both
added assertions as expected: missing `Block 1 of 6` (DOM showed block six), and
non-null draft after decline. The other 11 copied tests were filtered out, not
acceptance skips. No temporary test source was added to the repository.

Minimal reproduction steps for adding permanent regressions to the existing
component `describe` block:

1. Resolve `getCandidateInvite` to
   `candidateInvite({can_start_assessment: true, decision: 'consent'})`. Click
   the skip checkbox and Continue for each of six blocks (Review answers on the
   sixth). Click Clear device data, then Continue assessment. Assert Block 1 of
   6 and complete the journey again.
2. Set the draft key to a `CandidateDraftSchema`-valid envelope using the
   current definition ID/version and `saved_at: new Date().toISOString()`.
   Resolve the initial invite to `candidateInvite()` and the consent response to
   `candidateInvite({decision: 'decline', status: 'declined'})`. Click I
   decline, await the declined heading, and assert the draft key is null without
   reload.

## Combined regression handoff after 6C and dependency fixes

**Not executed by this review.** Coordinator must first freeze a clean
integration revision containing backend 6C, candidate UI 6C, dependency fixes,
and any R1/R2 fixes. Record their actual integrated hashes; this report's
`c20b3ed` is not that future revision. Record Node/Python versions and installed
lockfile hashes after the dependency owner performs the clean install. Do not
reuse pre-fix container images or cite earlier browser results for this
revision.

Run this bounded combined selection in the clean dedicated checkout:

```sh
git rev-parse HEAD
git status --porcelain
shasum -a 256 package-lock.json tests/browser/package-lock.json
node --version
.venv/bin/python --version
(cd apps/web && ../../node_modules/.bin/vitest run \
  lib/candidate-storage.test.ts \
  'app/candidate/invites/[token]/candidate-assessment.test.tsx')
.venv/bin/python -m pytest -q -o addopts='' tests/browser/test_scaffold.py
.venv/bin/python -m pytest -c apps/api/pyproject.toml -q -o addopts='' \
  apps/api/tests/test_database_migrations.py \
  apps/api/tests/test_invitations.py apps/api/tests/test_reports.py
docker compose -f deploy/compose.yaml config --quiet
docker compose -f tests/browser/compose.yaml config --quiet
```

The API selection uses temporary SQLite fixtures. Add the exact new 6C
historical registry/populated-upgrade test files from that worker's final
manifest if they are separate files; their names and result counts are not yet
known at this revision. Require actual coverage of outstanding v1 invite, saved
v1 draft, submitted assessment, persisted v1 report, unknown versions, retired
assignment policy and populated migration backfill. Existing migration tests
alone do not prove those cases.

For the PostgreSQL portion, reserve **5563 / iopsych_review** exclusively; never
point this command at the existing database or reuse another worker's server.
Create only a fresh synthetic disposable container, then run:

```sh
# bash; run only after confirming 5563 is free and Docker context is local.
set -euo pipefail
review_container="iopsych-review-$(python3 -c 'import uuid; print(uuid.uuid4().hex[:12])')"
review_id=$(docker run -d --name "$review_container" \
  --tmpfs /var/lib/postgresql/data -p 127.0.0.1:5563:5432 \
  -e POSTGRES_USER=iopsych_review -e POSTGRES_DB=iopsych_review \
  -e POSTGRES_PASSWORD=synthetic-local-only postgres:16-bookworm)
trap 'docker rm -f "$review_id" >/dev/null' EXIT
for attempt in $(seq 1 30); do
  if docker exec "$review_id" pg_isready -U iopsych_review -d iopsych_review; then
    break
  fi
  sleep 1
done
docker exec "$review_id" pg_isready -U iopsych_review -d iopsych_review
TEST_POSTGRES_URL='postgresql+psycopg://iopsych_review:synthetic-local-only@127.0.0.1:5563/iopsych_review' \
DATABASE_URL='postgresql+psycopg://iopsych_review:synthetic-local-only@127.0.0.1:5563/iopsych_review' \
.venv/bin/python -m pytest -c apps/api/pyproject.toml -q -o addopts='' \
  apps/api/tests/test_reports_postgres.py
```

The existing PostgreSQL tests own UUID schemas, migrate and seed within them,
and drop only those test schemas. The disposable container adds independent
isolation. Require zero skipped PostgreSQL cases and retain the migration head,
image digest, revision, command and result. Apply new 6C PostgreSQL upgrade
tests here as specified by their owner; do not run destructive migration probes
on an existing database.

**12A owner only:** after the same revision and clean install, and after its
allocated ports are released, run `scripts/browser-e2e.sh`. The reviewed runner
hardcodes **3104/8104/5544/1124/8124**; this review's **3123/8123** allocation
does not override them. Do not start a second browser runner or build in its
checkout. Require assigned-version fixture compatibility and add real browser
recovery coverage; the current three-test scaffold cannot close those gates.
Verify owned process/container cleanup after success and controlled failure.

**11A owner only:** rebuild API and web sequentially with
`REVISION=$(git rev-parse HEAD)` using the commands in `deploy/README.md`, once
3106/8106/5546 and that rehearsal project are explicitly available. Record fresh
image IDs/digests and migration head, inspect historical definition assets in
the API image, and rerun migration, non-root identity, private web-to-API,
unauthenticated proxy, and stop/restart probes. Do not delete the existing 11A
volume or reinterpret the idle restart as rollback acceptance. A separate
populated prior-version upgrade and previous-image compatibility rehearsal
remain required. Ports 3000/8000/8001 remain untouched throughout.

This handoff closes the bounded review only. It does not claim 6C, 9A, 11A, 12A,
hosted security, real-provider, scientific, privacy or product acceptance.
