# 12A integrated production browser verification

Date: 2026-11-04. Child branch: `AbhiNutakki/iopsych-browser-integrate`. This
report covers local synthetic production Chromium verification only; full
12A/12B acceptance remains open.

## Fixture correction and regression

Direct browser invitations now receive the immutable snapshot returned by
`new_assignment(allow_synthetic=True)`. The owned runner explicitly sets
`INVITE_ALLOW_SYNTHETIC_DEFINITIONS=true`; no definition is relabeled reviewed
and no application authorization or version checks are bypassed. The default
production synthetic policy remains unchanged.

The original ten cases remain enabled. An eleventh case uses its own disposable
invitation to reach review, clear device data, verify no candidate storage keys
remain, continue at block one with no selected answers, refill every block with
empty initial selections, review and submit successfully, and reload completion.
Five synthetic invitations now produce five messages in local Mailpit. Existing
report and privacy cases still consume the original fixtures.

## Exact revisions and results

- Initial integrated run: `0dbb95eaf1211d63c426e9f57fe4e5c9757e7dea`, comprising
  coordinator `fb7a4046efc477c268c90fc7a53f8eeec4f06e17` and fixture correction
  `12704c6`. `bash scripts/browser-e2e.sh` exited 0: **10 passed, 0 failed, 0
  skipped (14.1 seconds)**. All 24 axe scans reported zero violations. This
  verifies the integrated cookie sign-out and profile contrast fixes.
- Recovery run source: `b06453c2ce26eee95553c7609379395aadb7f0af`, containing
  coordinator `b8434fe2037d1b986743990bdfa87a0bc1beef95` including recovery fix
  `df9a7fb`. `bash scripts/browser-e2e.sh` exited 0: **11 passed, 0 failed, 0
  skipped (17.4 seconds)**, including the separate clear-at-review case. All 27
  axe scans reported zero violations.
- `.venv/bin/python -m pytest tests/browser/test_scaffold.py -o addopts='' -q`:
  **17 passed** both before the initial run and after the recovery merge.
- `.venv/bin/python -m ruff check --config apps/api/pyproject.toml tests/browser/*.py scripts/browser-e2e.py`:
  passed. Only targeted tests and the runner's production build were run.

[Initial sanitized evidence](../../tests/browser/evidence/12a-integration-initial.json)
and
[recovery evidence](../../tests/browser/evidence/12a-integration-recovery.json)
contain exact revisions, result counts and static axe summaries only. Both runs
removed their owned containers and networks successfully. Final Prettier and
`git diff --check` passed.

## Isolation and limits

The existing runtime preflight remains intact: inherited targets/credentials and
proxies are rejected, Docker must be local, local dotenv files are rejected, and
all allocated ports must be free. Each run creates a uniquely named Compose
project with fresh PostgreSQL tmpfs and Mailpit without forwarding, applies all
eight migrations, and cleans only its own resources. Ports are web 3116, API
8116, database 5556, SMTP 1136 and mailbox HTTP 8136. Ports 3000/8000/8001 and
existing databases are untouched.

Short-lived synthetic credentials use the real verifier and session exchange.
Browser traffic is restricted to the owned web origin. Temporary server logs,
browser diagnostics and downloads are removed; bearer credentials are redacted
before output. No screenshots, traces, raw answer payloads or exports are
retained. Build-generated `apps/web/next-env.d.ts` changes are restored, not
committed.

Axe incomplete checks still need manual review; zero automatic violations does
not establish WCAG conformance. No provider smoke, manual assistive-technology
assessment, staging/HTTPS verification, scientific approval, real email, public
deployment, purchase, push or existing-database reset was performed. Invitation
management UI, hosted checks, full lifecycle/upgrade evidence and external
review remain separately owned gates. This run does not claim those packages
complete.
