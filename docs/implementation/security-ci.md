# Independent security CI gates

Implemented on November 4, 2026 in `AbhiNutakki/iopsych-security-ci`, based on
`c20b3eddc21f73870a87fb27503151da43be8048`. This is a bounded security CI
change, not package 12A completion or deployment/pilot approval. The applicable
plans, progress ledger and `12a-security-review.md` were reviewed; no ancestor
or root AGENTS.md applied to the owned paths.

## Changes

The existing `.github/workflows/security.yml` now has independent JavaScript,
Python and secret jobs. None depends on another scanner's success. A high or
critical npm advisory therefore cannot suppress Python or secret scanning.
Python installation uses the existing shell installer without needing Node. The
existing `dependencies` job name remains as an always-evaluated aggregate: only
success from all three scanner jobs passes; failure, cancellation or skips fail
the gate. No continue-on-error or advisory suppression was introduced.

Gitleaks remains pinned to 8.24.3 with the existing default rules and sole exact
public synthetic-fixture exception. The secret job checks both the current
working directory (`dir .`) and all available Git refs
(`git . --log-opts=--all`) after full-history checkout. The directory scan
includes local uncommitted files; no new path exclusion was added. Gitleaks' own
binary/symlink handling and detector limitations still apply. CI has a fresh
checkout, not a developer's ignored local configuration.

`scripts/security-secrets.py` attempts both scopes even if the first fails,
reports findings separately from operational errors, and fails closed for
missing, malformed or inconsistent reports, missing executables and timeouts.
Scanner stdout/stderr are discarded. Redacted intermediate reports live in a
private temporary directory and are deleted; only status, exit code and counts
are printed and uploaded. Paths, commit messages, matches and credential values
are not retained in secret artifacts. Each scope has an eight-minute timeout.
The wrapper's four focused regression tests run in the secret job.

Dependency artifacts remain separate JSON reports, with no secret report glob.
All three artifacts use 14-day retention and upload even after scan failure. The
former combined `dependency-scans` and raw `secret-scan` artifact names are
replaced by `javascript-dependency-scan`, `python-dependency-scan` and
`secret-scan-counts`. Existing historical documentation describes older runs;
this report describes the current workflow. Hosted branch protections were not
queried or changed.

## Executed validation

Commands ran only in this child worktree; no application/server/database or
browser test was started, and no allocated or protected port was used.

| Command                                                                                                                      | Actual result                                                                                                                       |
| ---------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| `npm ci && PYTHON_BIN=python3.12 npm run api:install`                                                                        | Exit 0; both setup stages completed                                                                                                 |
| `.venv/bin/pip check`                                                                                                        | Exit 0; no broken requirements                                                                                                      |
| `npm audit --audit-level=high --json`                                                                                        | Exit 1; 15 package entries: 11 moderate, 3 high, 1 critical                                                                         |
| `.venv/bin/pip freeze --exclude-editable > /tmp/iopsych-security-tools/api-dependencies.txt`                                 | Exit 0; excludes the editable local package only                                                                                    |
| `/tmp/iopsych-security-tools/audit/bin/pip-audit -r /tmp/iopsych-security-tools/api-dependencies.txt --strict --format json` | Exit 0; 41 packages, zero known vulnerabilities, pip-audit 2.10.0                                                                   |
| `GITLEAKS_BIN=/tmp/iopsych-security-tools/gitleaks python3.12 scripts/security-secrets.py`                                   | Exit 0; current checkout: 0 findings, exit 0; all-ref history: 0 findings, exit 0                                                   |
| `python3.12 -m unittest discover -s scripts -p test_security_secrets.py -v`                                                  | Exit 0; 4 tests pass, including eight operational/inconsistent-report subcases, independent history execution and disclosure checks |
| `.venv/bin/python -m ruff check scripts/security-secrets.py scripts/test_security_secrets.py`                                | Exit 0                                                                                                                              |
| `.venv/bin/python -m ruff format --check scripts/security-secrets.py scripts/test_security_secrets.py`                       | Exit 0                                                                                                                              |
| `/tmp/iopsych-security-tools/actionlint .github/workflows/security.yml`                                                      | Exit 0; actionlint 1.7.7                                                                                                            |
| `npx prettier --check .github/workflows/security.yml docs/implementation/security-ci.md`                                     | Exit 0                                                                                                                              |
| `git diff --check`                                                                                                           | Exit 0                                                                                                                              |

A local PyYAML topology assertion also verified that the three scanner jobs have
no dependencies or continue-on-error setting, then executed the actual aggregate
Bash step over all 64 success/failure/cancelled/skipped combinations: only three
success results passed.

Local Gitleaks was downloaded from the official 8.24.3 Darwin ARM64 release; its
archive SHA256 matched that release's checksum manifest before extraction. CI
continues to build the pinned Go module. Local pip-audit lives in a separate
temporary virtual environment, installed with `pip-audit==2.10.0`; neither tool
changed application dependencies. Raw local dependency audit output was held
under `/tmp/iopsych-security-tools/`, not committed or externally uploaded.

Additional bounded configuration inspection found zero non-template dotenv files
outside installed dependencies and zero nonempty common provider/cloud
credential environment variables (OpenAI, Anthropic, AWS access/secret keys,
Azure client secret, Google credential path, Resend, SendGrid and OIDC client
secret). Values were never printed. Together with fresh source/history scans,
this found no provider/cloud credentials in the inspected scope; it does not
prove absence of unrecognized credentials, external secret stores or refs not
available to this checkout. No credentials were sent to providers for
validation.

## Remaining work and handoff

The npm findings still block the security gate at this baseline. Remediation
belongs to the assigned dependency owner; no manifest, lockfile or application
finding was changed here. Re-run audits after integrating that owner's changes,
and scan the final integrated revision/history. Python is clean for the
installed graph assessed here, not a promise about future resolution or
advisories.

Hosted GitHub execution, required-check configuration and hosted artifacts
remain unverified because pushing/running hosted workflows was outside
authorization. Local workflow lint and wrapper tests are not a hosted execution
claim. No browser CI, scientific/product/provider approvals, release readiness
or external upload is included in this change. There are no migrations or
contract changes.
