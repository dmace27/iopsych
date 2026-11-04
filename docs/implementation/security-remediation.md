# Bounded JavaScript dependency remediation

Completed November 4, 2026 in `AbhiNutakki/iopsych-security-fixes`, based on
`c20b3ed`. This report accompanies the remediation commit; it is not package 12A
completion or release approval. The integrated
[security assessment](12a-security-review.md) and its evidence supplied the
baseline: 15 vulnerable package entries (11 moderate, three high, one critical),
including two production entries. Registry metadata was checked again locally.

## Changes and compatibility

- Next and eslint-config-next: 16.3.8 → 16.4.1, including matching Next binaries
  and ESLint plugin. React stays 19.3.0, within Next's published peer range.
- Shared Zod: 4.6.5 → 4.6.6. No contract, generated schema, definition, scoring,
  or migration changes.
- Web/shared Vitest and web coverage-v8: 5.0.2 → 5.0.3, with matching
  mocker/spy. Vitest now pins why-is-node-running 3.2.1, accounting for its
  3.2.2 → 3.2.1 change. The coverage provider stays hoisted beside Vitest.
- Lock-only Vite 8.3.1 → 8.3.3 and Undici 8.11.2 → 8.12.2 satisfy Vitest's
  `^6.4.0 || ^7.0.0 || ^8.0.0` and jsdom's `^8.10.2` requirements. No direct
  dependency or persistent override was added for either.
- Scoped override: `@typescript-eslint/typescript-estree` → minimatch 11.0.1.
  This deliberately overrides the parent's `^10.2.2` requirement; unrelated
  minimatch 3.1.5 remains unchanged. Its new dependency
  `@isaacs/nonrecursive-glob-match` resolves to 1.0.3.
- Node engines now specify `^22.22.2 || ^24.15.0 || >=26.0.0`; `.nvmrc` selects
  22.22.2. Existing jsdom 30.1.1 and npm-run-all2 9.0.3 already require this
  floor, stricter than Undici's >=22.19.0 and Vitest's >=22.12.0 on Node 22.
  Execution here used Node 24.21.0, npm 11.19.0, Python 3.12.16 on macOS.

The narrow lock refresh used
`npm install --package-lock-only --ignore-scripts --no-audit`, and
`npm update minimatch undici --package-lock-only --ignore-scripts --no-audit`,
with temporary exact Vite/Undici constraints removed afterward. Unrelated
resolution churn was restored to baseline entries. A trial
`npm dedupe @vitest/coverage-v8 --package-lock-only --ignore-scripts --no-audit`
did not hoist coverage and updated unrelated transitive packages; those changes
were removed. The final lock explicitly retains coverage at its original root
location and was verified by a fresh `npm ci --no-audit`.

## Commands and results

All commands ran inside this child worktree. No app server, database, mail,
provider, deployment, or protected port was used.

| Command                                                                                                                                                            | Result                                                                                                                                         |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| `npm view next@16.4.1 version engines peerDependencies --json` (and equivalent views for eslint-config-next, Zod, Vitest, coverage-v8, Vite, Undici and minimatch) | Published requested versions and compatible peers confirmed.                                                                                   |
| `npm ci && PYTHON_BIN=python3.12 npm run api:install`                                                                                                              | Exit 0; saved setup completed, including editable shared Python package.                                                                       |
| `npm ci --no-audit` on the final lock                                                                                                                              | Exit 0; 471 packages installed.                                                                                                                |
| `npm ls next eslint-config-next zod vitest @vitest/coverage-v8 vite undici minimatch`                                                                              | Exit 0; exact requested versions and scoped override confirmed.                                                                                |
| `npm audit --json`                                                                                                                                                 | Exit 0; zero vulnerabilities at every severity.                                                                                                |
| `npm audit --omit=dev --json`                                                                                                                                      | Exit 0; zero production vulnerabilities.                                                                                                       |
| `npm run lint --workspace @iopsych/web`                                                                                                                            | Exit 0.                                                                                                                                        |
| `npm run lint --workspace @iopsych/shared`                                                                                                                         | Exit 0; includes typed ESLint project-service parsing.                                                                                         |
| `npm run typecheck --workspace @iopsych/shared`                                                                                                                    | Exit 0.                                                                                                                                        |
| `npm run typecheck --workspace @iopsych/web`                                                                                                                       | Exit 0; Next route generation and TypeScript passed. Generated next-env path changes were restored to avoid app-source edits.                  |
| `npm run test --workspace @iopsych/shared`                                                                                                                         | Exit 0; 99 tests in three files.                                                                                                               |
| `npm run test --workspace @iopsych/web`                                                                                                                            | Final exit 0; 136 tests in 25 files, all configured coverage gates passed. Statements 90.76%, branches 86.28%, functions 89.91%, lines 92.03%. |
| `npm run schemas --workspace @iopsych/shared && git diff --exit-code -- packages/shared/schemas packages/shared/definitions`                                       | Exit 0; no generated contract/definition drift.                                                                                                |
| `git diff --check`                                                                                                                                                 | Passed.                                                                                                                                        |

The initial web coverage attempt failed before tests because npm nested
coverage-v8 under apps/web while the hoisted Vitest imported it from root.
Hoisting its lock entry and reinstalling resolved this; the final web run above
used the narrowed final graph. No application-source workaround was needed.
Lint/types/shared tests ran against the same dependency versions as the final
graph; the only later effective correction was coverage-provider placement.

## Focused compatibility probes

A Node assertion probe compared all 64 combinations of eight filenames and eight
glob patterns with `{ dot: true }`, saving minimatch 10.2.6 results before
installation and comparing 11.0.1 afterward. Filenames covered root/nested TS,
hidden files, tests, JSON and JS; patterns covered `*.ts`, `*.{ts,js}`,
`src/**/*.ts`, `**/.*.ts`, `!other.js`, `src/+(index|other).ts`, `**/*.test.ts`,
and `*.json`. All results matched. This is the API/options actually used by
estree's `useProgramFromProjectService.js`, not proof of all minimatch behavior.

A direct `@typescript-eslint/parser.parseForESLint` probe parsed
`const value: number = 1;` with filePath
`packages/shared/security-glob-probe.ts`, tsconfigRootDir `packages/shared`, and
`projectService: { allowDefaultProject: ['security-*.ts'] }`; the assertion that
`services.program` exists passed. No probe source file was written.

A bounded Zod probe rejected malformed arrays, sets and maps containing 1,024
invalid numeric values and accepted `[1, 2]` using `z.array(z.number())`. No
memory-exhaustion stress test was attempted. Shared contract fixtures and web
response/storage tests supply the application compatibility evidence.

## Residual limits and next work

- No known npm advisory remains in the final audit snapshot. An audit does not
  establish absence of undisclosed flaws, production exploitability, or release
  readiness. Node's separately bundled fetch/Undici is outside npm's graph.
- The minimatch override crosses a major boundary and needs removal when the
  upstream parent adopts a fixed supported range. Current glob and typed-parser
  checks support this narrow use; they do not guarantee arbitrary API parity.
- Engine-range assertions passed for 22.22.2, 24.15.0, 24.21.0 and 26.0.0 after
  excluding the existing optional `@img/sharp-win32-ia32` binary, whose metadata
  requires Node `^20.9.0`. An initial assertion across every optional platform
  failed on that entry. Windows 32-bit is not validated/supported by these
  checks; execution on Node 22 or other OSes remains an integration task.
- npm warns that ESLint 9.39.5 is no longer supported. Updating its major is
  outside this narrow advisory change. npm also reports unapproved install
  scripts for esbuild, fsevents and unrs-resolver; policy was not changed and
  the local checks passed with the existing policy.
- Production Next build, CSP/session/proxy HTTP smoke, browser/HTTPS flows,
  Linux packaging, Python audit, source/history secret scans and hosted CI
  remain the integration/security owners' work. No redundant API/full-monorepo
  suite was run. No scientific, product, provider, or pilot approval is implied.

Temporary raw logs/audit JSON are under `/tmp/iopsych-security-*` on this worker
machine, not durable release evidence. This report records the outcomes; rerun
audits and the planned integrated production checks at the merged revision.
