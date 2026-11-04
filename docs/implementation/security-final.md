# Final bounded security receipt

2026-11-04; baseline `59d3159`, with coordinator certifi fix `616b861`
cherry-picked as `2f4e56f`. No ancestor/root AGENTS.md applies to these paths.
Reviewed prior security CI, remediation, and credential-review receipts.

## Classification and minimal correction

The supplied scan had five tracked-source findings and eleven historical
findings. Three source findings and nine historical findings are synthetic
idempotency identifiers in defensive service tests (lines 195, 222, 229). The
remaining source findings are Docker image revision tags in packaging receipts;
the package-current tag also accounts for two history findings. No genuine
credential was identified among these findings. Only fifteen exact fingerprints
were added to `.gitleaksignore`; the three existing exceptions remain unchanged.
No rule/path suppression or history rewrite was introduced.

The original absolute archive path prepended its temporary directory to source
fingerprints, preventing existing relative exceptions from matching. Repeating
`gitleaks dir .` from the archive directory fixes that invocation issue. The
existing wrapper already uses relative `.` and needs no code/test change.

## Executed checks

| Check                                                                                                    | Result                                              |
| -------------------------------------------------------------------------------------------------------- | --------------------------------------------------- |
| Gitleaks version                                                                                         | 8.24.3                                              |
| Tracked archive `dir .`, checked-in config, updated exact ignores                                        | Exit 0, zero findings                               |
| Repository `git . --log-opts=--all`, same config/ignores                                                 | Exit 0, zero findings                               |
| `npm audit --json`                                                                                       | Exit 0, zero vulnerabilities at every severity      |
| Installed graph `pip freeze --exclude-editable`, then isolated `pip-audit -r ... --strict --format json` | Exit 0, 52 dependencies, zero known vulnerabilities |
| `.venv/bin/pip check`                                                                                    | Exit 0, no broken requirements                      |
| `.venv/bin/pip install --dry-run -r apps/api/requirements-dev.txt` after coordinator fix                 | Exit 0                                              |
| `git diff --check`                                                                                       | Exit 0                                              |

The exact proposed/adopted constraint is `certifi==2026.10.23` in production
requirements, inherited by development requirements. Installed httpx 0.28.1 and
httpcore 1.0.9 both declare unconstrained `certifi`, so the pin satisfies their
metadata; installed certifi is 2026.10.23. This is above the
coordinator-provided 2026.10.19 fixed floor. Dependency edits belong to the
coordinator; this worker only integrated that existing commit and verified
resolution/audits.

## Limits and handoff

Source evidence covers tracked files exported from the integrated worker HEAD
with the pending exact ignore changes, not ignored working-directory artifacts.
History means all locally available refs, without remote fetching. Raw scanner
output was kept outside the repository; no provider validation, mail, push, paid
calls, full test suite, build, or running application scan was performed. The
coordinator must rerun source/history scans after other workers and this receipt
are integrated, since new fixtures and commits can add fingerprints. Audits
describe this installed graph and public advisory snapshot only.
