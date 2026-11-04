# Next reconciled regression receipt

Reviewed `124f887ac9ce7381bec3ea8ceb6a002dafe4a35a` on November 4, 2026. This is
a preparation/targeted-check receipt, **not a green combined checkpoint**. Read
the final plan, MVP specification, finish review, frozen
[acceptance review](acceptance-current.md) at `eeea1da`, and progress's 23:23
current override. No ancestor/root/docs AGENTS was found; web AGENTS and
installed Next 16.4.1 CLI documentation were read (typegen, production
build/start). Live Orca metadata showed `GPT-6-Astra medium fast`; no toggle
occurred. Saved setup terminal emitted `__ORCA_SETUP_COMPLETE__` with exit 0
before tests. Only this file changes; no database/container, provider, real mail
or protected port was used. Coordinator owns integration; remote lead owns
migrations/dependencies.

Actual ancestry contains `f2e6329` (historical seed repair), `f6139e7`
(defensive coverage), `97750a5` (notice0011), `3a91017` (wire/export), and
`34e1749`/`f81d530`/`e76ef02` (UI). The old `b22c7aa` result of 934 passes, two
failures and 99.83% coverage remains a failed historical checkpoint, not the
current result. Remote `646201a` contains Auth0 verification/provider web login,
Resend adapter/outbox, and `docs/decisions/structure-comparison.md` recording
the owner's November 3 direct-v2 decision. Those implementations are selected;
they are not yet ancestors of this inspected child HEAD. Do not confuse their
presence in the repository with successful reconciled integration or hosted use.

## Executed checks

Both commands ran from root with an allowlisted environment and no dotenv files:

```sh
env -i PATH="$PATH" HOME="$HOME" TMPDIR="${TMPDIR:-/tmp}" .venv/bin/python -m pytest -c apps/api/pyproject.toml apps/api/tests/test_notice_snapshot.py apps/api/tests/test_notice_snapshot_api.py --no-cov -q
env -i PATH="$PATH" HOME="$HOME" TMPDIR="${TMPDIR:-/tmp}" .venv/bin/python -m pytest -c apps/api/pyproject.toml apps/api/tests/test_invitations.py apps/api/tests/test_privacy.py apps/api/tests/test_privacy_related_audit.py apps/api/tests/test_database_migrations.py apps/api/tests/test_reports.py --no-cov -q
```

Results: **64 passed** (one existing Starlette/httpx deprecation warning), then
**38 passed**, both exit 0, zero skips. These are the 102 non-PostgreSQL cases
from the notice owner's 105-case command, executed once each. The three notice
PostgreSQL cases were not invoked; no concurrency/PG or coverage acceptance is
claimed. `--no-cov` is confined to these targeted checks, never the final gate.

## One final combined run, after remote checkpoint

Freeze the reconciled SHA, inspect its scripts/fixtures again, and wait for its
saved install to finish. Do not run both `npm run check` and the decomposition
below: that duplicates suites. Use a fresh child with no local dotenv files,
allowlist PATH/HOME/TMPDIR plus explicit synthetic test settings, and run these
stages serially with separately retained exit codes (continue collecting
failures, but require every stage to pass):

```sh
git rev-parse HEAD
npm run format:check
npm run lint
npm run typecheck
npm run test:js
npm run test:contracts:python
.venv/bin/python -m pytest apps/api --cov-config=apps/api/pyproject.toml
npm run build
npm run schemas --workspace @iopsych/shared
git diff --exit-code -- packages/shared/schemas
npm run db:migrate
npm run db:seed
npm run db:verify
npm run security:smoke
.venv/bin/python -m pytest scripts/verification --no-cov -q
.venv/bin/python -m unittest discover -s scripts -p test_security_secrets.py -v
npm audit --audit-level=high --json
.venv/bin/pip freeze --exclude-editable > /tmp/iopsych-next-api-dependencies.txt
# Use the security owner's isolated pip-audit 2.10.0 installation:
pip-audit -r /tmp/iopsych-next-api-dependencies.txt --strict --format json
# Use pinned gitleaks 8.24.3; wrapper publishes only sanitized counts:
.venv/bin/python scripts/security-secrets.py
git diff --check
```

API coverage explicitly loads the committed branch configuration on its
**first** run, avoiding the historical second full run. Keep the 100% API gate
and all web/ contract thresholds. Zero required skips is necessary. Record both
assertion and coverage failures. `db:*` requires DATABASE_URL pointing only to a
newly created owned synthetic database; security smoke creates/removes its own
schema and uses ephemeral API/web ports. Never inherit an ambient DATABASE_URL.
Audit tools belong to the security/dependency owner; missing tools are a
prerequisite, not permission to change manifests. Capture audit JSON privately;
do not expose secrets. The secret wrapper's source scan includes the working
directory, so run it in a clean checkout before generated artifacts, or
separately report tracked-export and working-directory scope; never call a
failed artifact scan clean.

**Allocation blocker:** reserved PG5615/5616/5617/5618 and mail1148/8148 do not
work with this HEAD's hardcoded guards. Escalated as `msg_07d766701383`. Do not
bypass guards or occupy another owner's ports. Current executable opt-in
settings, conditional on coordinator allocation of newly created resources, are:

| Setting                        | Guarded synthetic target                                                                |
| ------------------------------ | --------------------------------------------------------------------------------------- |
| `TEST_POSTGRES_URL`            | `postgresql+psycopg://synthetic:synthetic-local-only@127.0.0.1:5571/iopsych_regression` |
| `TEST_DELIVERY_POSTGRES_URL`   | `postgresql+psycopg://synthetic:synthetic-local-only@127.0.0.1:5586/iopsych_delivery`   |
| `ACCOUNT_TEST_POSTGRES_URL`    | `postgresql+psycopg://synthetic:synthetic-local-only@127.0.0.1:5594/iopsych_access`     |
| `READINESS_TEST_DATABASE_URL`  | `postgresql+psycopg://synthetic:synthetic-local-only@127.0.0.1:5573/iopsych_readiness`  |
| `NOTICE_TEST_POSTGRES_URL`     | `postgresql+psycopg://synthetic:synthetic-local-only@127.0.0.1:5603/iopsych_notice`     |
| `IOPSYCH_TEST_LOCAL_MAILPIT=1` | SMTP1139 / HTTP8139, no relay                                                           |

Launcher additionally binds8113; readiness stall test binds8133. Remote provider
fixtures may add allocations after reconciliation. Four reserved PG listeners
could host five separate synthetic databases if guards are safely parameterized;
this receipt does not authorize such edits. Reserve each socket before creation,
require local Docker context, label owned containers, and remove only those
owned resources. Preserve3000/8000/8001/5432 and all existing databases.

Browser owner runs
`env -i PATH="$PATH" HOME="$HOME" TMPDIR="${TMPDIR:-/tmp}" .venv/bin/python scripts/browser-e2e.py`
once at the same frozen SHA after obtaining3116/8116/5556/1136/8136. That
harness builds internally; schedule its build rather than redundantly rebuilding
solely for browser launch. It cannot presently use this worker's reserved ports.
Populated remote-lineage bridge verification remains the migration owner's
separate required receipt; an empty `upgrade head` is insufficient. No stamping,
resetting, or arbitrary merge-head traversal is an acceptable substitute.

## All 21 package acceptance gaps after evidence reconciliation

Every row remains partial or needs current-revision evidence; this receipt
grants no new full-package acceptance. Existing detailed evidence remains in the
frozen acceptance report and later revision-linked receipts.

| Package | Remaining evidence or gate                                                                                                                                                                                                                                          |
| ------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 6A      | One README-only clean-checkout rehearsal on reconciled dependencies/migrations, including actual launcher and synthetic login. Earlier setup evidence remains valid only at its recorded revision.                                                                  |
| 6B      | Auth0/Resend selected and direct-v2 product interpretation recorded; remaining organization, hosting, resume/context, notes and review-state decisions plus conflicting spec reconciliation need accountable records. Independent I-O/privacy approval is separate. |
| 6C      | Reconciled populated upgrade from supported histories, v1 retained assignments/drafts/reports and v2 assignment/trace compatibility; reviewed real-pilot content eligibility still absent.                                                                          |
| 7A      | Merge Auth0 API/web contracts; configured independent recruiter/manager sign-in, callbacks/invalid claims/expiry/recovery and HTTPS cookies. Local tests do not prove credentials work.                                                                             |
| 7B      | Existing account mutation/browser evidence and rollback guard are integrated; controlled initial provisioning, stable provider-subject mapping, explicit organization policy and reconciled access enforcement still need evidence.                                 |
| 7C      | Explicit submit/review/request-edits/reject with attribution/reasons, stale-state protection and actionable browser revision loop; approved notes workflow remains. Metadata/archive is already implemented.                                                        |
| 8A      | Reconcile local encrypted queue and distinct Resend outbox; preserve uncertainty/idempotency/cancellation/webhook states and migrated data; controlled staging mailbox/consent proof, domain/credential/key-custody and operational recovery evidence remain.       |
| 8B      | Issuance proxy, recovery and delivery-state UI are integrated; final approval-to-invite chain, provider negatives and truthful consent/submission/expiry presentation at reconciled SHA remain, together with 7C/8A dependencies.                                   |
| 9A      | Storage denial/reload/stale-clear fixes already exist; consolidate final candidate/browser evidence across denied writes, expiry and assigned versions after visual/notice changes.                                                                                 |
| 9B      | Recorded server-resume/context implementation or explicit approved scope revision; existing device-only behavior does not fulfill cross-device or optional-context promises.                                                                                        |
| 9C      | Direct-v2 product decision exists; integrated dual-language extremes, v1 replay, retained report hash/trace and new v2 evidence require verification. Scientific validity/content/threshold approval remains external.                                              |
| 10A     | Notice freeze and digest/export compatibility are integrated, not absent; non-submitted category clocks/rights, withdrawal/correction, identity verification after expiry and draft/context policy remain. Existing deadlines must survive upgrades.                |
| 10B     | Related-audit API/UI, exact lookup and stale-feedback repair/browser evidence exist; durable deleted-report lineage, verified-contact request handling and invite-only rights remain incomplete.                                                                    |
| 10C     | Bounded backlog drain and synthetic deletion-replay rehearsal exist; authoritative production journal capture/completeness, unattended scheduler/alerts, all lifecycle categories and approved clocks remain.                                                       |
| 11A     | Clean web/API packaging repair and release attribution exist; final reconciled images, populated migration compatibility, hosted topology/TLS/private ingress/privileges and safe rollback/forward-fix evidence remain.                                             |
| 11B     | Existing body/time/readiness/extraction bounds remain; measure slow synchronous DB isolation, distributed ingress fairness and actual configured extraction smoke in staging.                                                                                       |
| 11C     | Correlation/release logs and local restore evidence exist; cross-layer redaction, alert receivers/responders, encrypted hosted backups, measured RPO/RTO and authoritative replay remain.                                                                           |
| 12A     | One frozen combined gate with zero required skips, updated production browser/provider and populated migration checks, fresh security scans, HTTPS staging and required hosted CI/release checks.                                                                   |
| 12B     | Updated browser axe/reflow/focus evidence after UI changes plus manual keyboard/screen-reader/device/contrast and intended-user timing/comprehension; automated scans alone cannot close it.                                                                        |
| 12C     | Named operational/support owners, working contacts, full staging failure/rights/retention/restore rehearsal, training and actual content/privacy sign-offs.                                                                                                         |
| 12D     | Controlled synthetic demo/walkthrough and measured release handoff after technical gates; license/contribution/limitations evidence and explicit publication authorization remain. No push/deployment authorized here.                                              |

Smallest next safe engineering slice: have the coordinator assign **only
isolated test-target parameterization**, retaining numeric-loopback/database
allowlists, query/override rejection and ownership safety tests, to unlock the
final gate on reserved ports. No schema/provider/product changes are needed for
that slice. After that, the next bounded runtime investigation is synthetic
slow-DB versus unrelated-health latency, preserving transaction/audit atomicity;
change execution ownership only if measured blocking is reproduced. Neither is a
new dispatch here. Do not reassign already-owned Auth0/v2/notice/migration/UI
work or repeat completed release-ID wiring, audit discovery, notice inventory or
local replay preparation.

Product decisions, scientific content approval, privacy policy, provider
credentials/ verified domains, hosted operations, manual usability and
publication authorization are distinct gates. Synthetic mocks, fixture approval
flags and passing unit tests do not close them. Final serial integration and the
reconciled aggregate stay with the coordinator; no full suite was started before
the remote checkpoint.

Receipt validation: Prettier check and `git diff --check` passed; a focused row
check confirmed all 21 final-plan package identifiers are present.
