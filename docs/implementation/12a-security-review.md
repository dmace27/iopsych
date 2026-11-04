# 12A bounded security and dependency assessment

Assessed integration `16c461a45b3dcd8b27e560fa15a2a616fdfe5c61` on November 4,
2026, in isolated branch `AbhiNutakki/iopsych-12a-security`. This is evidence
and an allocation proposal, **not completion of package 12A or release
approval**. Root manifests, lockfile, application code, CI, integration branch
and databases were not changed. No app suite, build, deployment, exploit, mail
or port was run.

## Evidence and scope

Read `final-implementation-plan.md`, security/acceptance portions of
`mvp-spec.md`, `docs/implementation/progress.md`, `12ab-audit.md`, security
workflow, existing security evidence documentation and scanner configuration. No
ancestor/root AGENTS file was found; `apps/web/AGENTS.md` requires local Next
documentation before code changes, and no code was changed.

The checkout was at the requested revision, node_modules existed, and no active
npm ci/bootstrap process was observed. This worker did not reinstall
dependencies. Audits describe the committed root lockfile, not a new
clean-install verification. Local runtime was Node 24.21.0/npm 11.19.0; CI
selects Node 22 via `.nvmrc`.

- [Full npm audit](../security/evidence/final-implementation/npm-audit.json):
  **15 vulnerable package entries: 11 moderate, 3 high, 1 critical**.
- [Production-only audit](../security/evidence/final-implementation/npm-audit-production.json):
  **2 entries: Next critical and Zod high**. Both audit commands report
  vulnerabilities.
- [Exact affected instances](../security/evidence/final-implementation/affected-packages.json),
  [candidate registry metadata](../security/evidence/final-implementation/candidate-versions.json),
  [official advisory metadata](../security/evidence/final-implementation/advisory-metadata.json),
  and
  [revision/runtime/hash/limitations](../security/evidence/final-implementation/assessment.json).

The 15 count includes propagated parent findings; it is not 15 independent
exploits. There are 21 distinct advisory URLs across six directly affected
package families. Historical zero-vulnerability reports predate this assessment.
GitHub's public advisory API returned HTTP errors for seven records; their
advisory pages were inspected separately. No credentials/configuration were
collected in these evidence files.

## Runtime findings and observed reachability

| Dependency  | Evidence and prerequisites                                                                                                                                                                                                                                                                                                           | Assessment                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Next 16.3.8 | [Image optimization RCE](https://github.com/vercel/next.js/security/advisories/GHSA-2464-fhr4-w9xw), [App Router Server Action DoS](https://github.com/vercel/next.js/security/advisories/GHSA-p3m5-59mp-jv5r), [cached typed-array RCE](https://github.com/vercel/next.js/security/advisories/GHSA-673q-mjm6-r5xr); fixed in 16.4.1 | Runtime dependency, critical audit entry. Image advisory concerns glibc Linux and documents Sharp >=0.35.5 as workaround; lock already resolves Sharp 0.35.5. No `next/image` imports or SVG opt-in found. No `use server`, `use cache` or cacheComponents setting found in app/lib/config. Server Action and typed-array prerequisites were not observed. These are static observations, not proof of production immunity; upgrade remains recommended by maintainer.                                                                                                                                                                            |
| Zod 4.6.5   | [Collection-validation memory exhaustion](https://github.com/advisories/GHSA-mrhx-c7xc-m3w5); fixed 4.6.6                                                                                                                                                                                                                            | Runtime through shared contracts and browser validation. Unbounded arrays exist in `apps/web/lib/contracts.ts` (role lists/assumptions), `privacy-contracts.ts` (audit/export collections), and shared extraction/problem schemas. `api-client.ts` and `candidate-api.ts` parse API responses with safeParse; candidate storage also parses browser JSON. Malicious oversized malformed data can threaten the validating JS process/browser. No public server-side Zod exploitation path was demonstrated; API server validation is Python. Title and description differ on constraints, so do not assume `.max()` alone eliminates the advisory. |

## Development/tooling findings

| Family and exact versions                                         | Path and impact                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| ----------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Undici 8.11.2 (high)                                              | `@iopsych/web` devDependency jsdom 30.1.1 → undici `^8.10.2`. Eight advisories cover response/TLS process crashes, SSE/WebSocket memory growth, SRI checking, custom TLS callbacks, redirect/shared-cache confusion and decompression handlers. Their prerequisites require relevant APIs and attacker-controlled peers/responses. This lockfile instance is dev-only; no application import of Undici was found. This does **not** assess Node's separately bundled Undici/global fetch. |
| Vite 8.3.1 (high)                                                 | Vitest peer dependency, dev-only. Six advisories cover editor launching (including Windows/WSL-specific conditions), custom HTML middleware, filesystem allowlist bypass and Wasm error disclosure. Scripts use Next for app dev/build/start, and Vitest run for tests; no application Vite server configuration was observed. Exposing a separately configured Vite server would change the assessment.                                                                                  |
| Vitest, @vitest/mocker, @vitest/coverage-v8 5.0.2 (moderate each) | Mock registration injection and Windows traversal affect a reachable Vite HMR socket with public mockerPlugin/interceptorPlugin handlers. Checked Vitest config uses Node/jsdom tests without those explicit plugins. Advisory says Browser Mode does not register the affected traversal handlers. No exposed handler or exploit was demonstrated.                                                                                                                                       |
| minimatch 10.2.6 (moderate)                                       | Nested below @typescript-eslint/typescript-estree 8.70.1. [Amplification advisory](https://github.com/isaacs/minimatch/security/advisories/GHSA-g3hv-75wg-m249) requires attacker-controlled patterns and optimizationLevel >=2. Installed estree call uses `{ dot: true }`, not that optimization setting; application input path not observed.                                                                                                                                          |
| Propagated lint findings (moderate each)                          | @typescript-eslint/eslint-plugin, parser, type-utils, typescript-estree, utils, and typescript-eslint are all 8.70.1; eslint-config-next is 16.3.8. These seven entries inherit minimatch exposure rather than seven separate flaws.                                                                                                                                                                                                                                                      |

All individual advisory IDs, ranges and titles are preserved in the npm JSON.
Official details:
[Undici advisories](https://github.com/nodejs/undici/security/advisories),
[Vite advisories](https://github.com/vitejs/vite/security/advisories),
[Vitest mock injection](https://github.com/advisories/GHSA-qxg6-89mg-rqv8),
[Vitest Windows traversal](https://github.com/advisories/GHSA-xp26-3454-mjgp),
[editor flags](https://github.com/advisories/GHSA-r825-w8mm-5pxw).

## Exact minimal remediation proposal for allocation

Allocate manifest/lock editing to one dependency owner. These are verified
published candidate versions and advisory fix boundaries, **not installed or
tested fixes**; regenerate the graph and audit it before asserting resolution.

1. `apps/web/package.json`: Next **16.3.8 → 16.4.1**, and eslint-config-next
   **16.3.8 → 16.4.1** to keep framework lint alignment. Retain React 19.3.0,
   which matches the candidate's peer range. npm audit instead suggests 16.4.5;
   16.4.1 is the smallest published 16.x fix for all three observed advisories.
2. `packages/shared/package.json`: Zod **4.6.5 → 4.6.6**. Audit suggests 4.6.7,
   but 4.6.6 is the minimal fixed release in the observed advisory.
3. Both web/shared Vitest pins **5.0.2 → 5.0.3**, plus web coverage-v8 **5.0.2 →
   5.0.3** together; candidate peers require matching versions and resolve
   mocker 5.0.3. Audit's 5.1.0 recommendation is not necessary merely to cross
   these advisory boundaries.
4. Refresh locked Vite **8.3.1 → 8.3.3** and Undici **8.11.2 → 8.12.2**. Both
   fit existing parent/peer ranges, so prefer a targeted lock refresh without
   new direct dependencies; review unrelated lock churn. Ensure the resulting
   installed graph uses at least these exact versions.
5. For minimatch, propose root override
   `"@typescript-eslint/typescript-estree": { "minimatch": "11.0.1" }`. This
   deliberately crosses the parent's `^10.2.2` requirement and needs
   compatibility validation. Even published typescript-eslint 8.72.1 still
   requests `^10.2.2`; an ordinary parent update cannot fix it today. Do not
   apply audit's suggested downgrades to typescript-eslint 8.36.0 or
   eslint-config-next 15.5.29 blindly. Keep existing overrides intact and do not
   globally replace safe minimatch 3.x instances used by other linters.

Candidate Undici requires Node >=22.19.0; Vitest requires ^22.12.0, ^24 or >=26.
`.nvmrc` selects 22 but root engines currently permit older 22 and odd majors.
Dependency owner should verify actual CI/bootstrap Node satisfies these floors;
metadata compatibility alone is not execution evidence.

Validation allocation: clean install and both audits once after the lock change;
web/shared lint (especially estree project globs), typecheck, shared
contract/schema fixtures and web Vitest coverage using the matched tools. Zod
owner should check schema generation drift and bounded malformed-array
regression behavior without an OOM stress test. Integration runner should reuse
its planned production build, CSP/session/proxy smoke and browser checks to
validate the Next minor upgrade; do not duplicate the full application suite in
this evidence task. A targeted estree/minimatch glob compatibility check is
required before accepting the major override. No migration or contract change is
proposed.

## Secret scanning and CI gaps

Existing `.github/workflows/security.yml` pins Gitleaks 8.24.3, fetches full
history, uses default rules with one exact public synthetic-fixture allowlist,
and runs `gitleaks git --redact` with findings exit code 1. JSON uploads use
`if: always()` with 14-day retention. It does not separately scan uncommitted
current files. Existing source/history JSON reports are historical evidence
only.

Neither Gitleaks nor TruffleHog was found via command lookup. Gitleaks was also
absent from the conventional Go, local-user, Homebrew and /usr/local binary
paths. No scanner was installed because this slice only calls for scanning with
an already available tool. **Current-source and full-history local scans were
not run and cannot be claimed clean.** This does not establish scanner absence
in all possible containers or nonstandard paths. No secret values were printed
or copied. A follow-up owner with the pinned tool should capture only redacted
reports and sanitized status, review findings without exposing matched values,
and scan the integrated revision/history before release acceptance.

The dependency job's npm audit fails on high/critical entries; later Python
installation/audit steps have normal success conditions and will therefore be
skipped after this failure. Artifact upload still runs. Allocate a CI owner to
consider independent jobs/steps so both dependency ecosystems produce evidence
on failure; no CI edits were made here. Python dependencies, hosted CI
execution, branch protections and fresh secret scans remain unverified in this
slice.

## Handoff

Only this report and `docs/security/evidence/final-implementation/` are owned.
Next eligible action is dependency-owner remediation and focused validation,
followed by integrated security scans and the existing 12A runner's evidence.
Full product journey, hosted staging, external decisions and release approval
remain outside this bounded assessment.
