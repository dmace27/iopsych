# Next.js lint dependency override

The root `package.json` overrides `fast-glob` **only within
`@next/eslint-plugin-next`** with this private workspace package. The upstream
dependency brings in `micromatch` and `braces`; all published `braces` versions
are affected by
[GHSA-vfj7-8cjw-p6xm](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm). No
advisory is suppressed and the dependency audit keeps its existing threshold.
The root also declares the adapter as the local `fast-glob` development
dependency so npm 10 consistently links it during `npm ci`; the plugin override
references that dependency with `$fast-glob`.

Next.js 16.3.8 uses only `globSync(pattern, { onlyDirectories: true })` in its
`getRootDirs` helper. This adapter implements that call using `tinyglobby`, with
directory expansion disabled and the original absolute-path and trailing-slash
behavior preserved. It is not a general replacement for every `fast-glob` API.

The integration tests in `apps/web/eslint.config.test.ts` exercise the actual
Next.js helper with explicit roots, globs, and arrays of roots. Run
`npm run test:js` and `npm run lint:js` when changing the override or updating
the lint plugin. Remove this workspace and its override when the upstream plugin
uses a dependency graph without the vulnerable package.
