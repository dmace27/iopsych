# 7A sign-out cookie fix

This bounded fix addresses production sign-out only. Full 7A, identity/provider
selection, account provisioning, session recovery UX and hosted HTTPS acceptance
remain pending. No provider choice, migration, dependency, local-session route,
proxy or UI change is included.

## Diagnosis and implementation

The browser worker reported DELETE `/api/session` returning 204 followed by GET
`/api/internal/roles` returning 200. Installed Next 16.4.1's
`ResponseCookies.delete(name)` serializes an empty value and epoch expiry
without preserving Secure, HttpOnly or SameSite. It defaults Path to `/`, so the
concrete failure is the missing Secure attribute: browsers reject that
expiration for the production `__Host-iopsych_internal_token`. Incoming Cookie
headers cannot supply the missing attributes.

POST and DELETE now share root-path, HttpOnly, Strict SameSite and environment
Secure settings. DELETE explicitly sets an empty cookie with Max-Age=0 and epoch
expiry. Neither operation supplies Domain, preserving host-only scope;
production retains the `__Host-` name and Secure requirement, while development
retains its unprefixed cookie usable on local HTTP. Origin/Fetch Metadata
defenses and no-store responses are unchanged. Expiration must occur on the
original host and compatible scheme; this does not introduce cross-host
sign-out.

## Verification

Executed November 4, 2026 in the dedicated session-fix worktree, Node 24.21.0,
Next 16.4.1. Read applicable web AGENTS, installed Next cookies/route-handler
guidance, accelerated implementation schedule, coordination progress and
relevant 6A/12A reports before editing.

| Command                                                                                                                                                                               | Result                                                                                      |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| `npm exec --workspace @iopsych/web -- vitest run app/api/session/route.test.ts lib/internal-session.test.ts --coverage.enabled=false`                                                 | 20 passed, 2 files, zero skips                                                              |
| `npm run build`                                                                                                                                                                       | Shared TypeScript and production Next webpack build passed, including Next TypeScript check |
| `npm exec --workspace @iopsych/web -- eslint app/api/session/route.ts app/api/session/route.test.ts app/api/session/route.browser-test.mjs --max-warnings=0`                          | Passed                                                                                      |
| `npx prettier --check apps/web/app/api/session/route.ts apps/web/app/api/session/route.test.ts apps/web/app/api/session/route.browser-test.mjs docs/implementation/7a-signout-fix.md` | Passed                                                                                      |
| `git diff --check`                                                                                                                                                                    | Passed                                                                                      |

Focused tests reload the actual route and session helper under both production
and development environments. They check exact cookie attributes for creation
and expiration (including absence of Domain), empty 204/no-store response, and
rejection without cookie mutation for missing provenance, hostile Origin despite
same-origin metadata, same-site metadata and null Origin. Existing tests retain
valid Fetch Metadata fallback, token validation, upstream failures and
throttling.

Independent Chromium test commands (run production after the build, before dev):

```sh
PLAYWRIGHT_MODULE_PATH=/Users/abhiramnutakki/orca/workspaces/iopsych/iopsych-12a-expand/tests/browser/node_modules/playwright/index.mjs node apps/web/app/api/session/route.browser-test.mjs
PLAYWRIGHT_MODULE_PATH=/Users/abhiramnutakki/orca/workspaces/iopsych/iopsych-12a-expand/tests/browser/node_modules/playwright/index.mjs node apps/web/app/api/session/route.browser-test.mjs --development
```

Both passed: initial roles 401 → sign-in 200 → roles 200 → DELETE 204 → cookie
absent → roles 401, with no upstream call after sign-out; repeated DELETE also
returned 204. The production browser accepted the Secure host-prefixed cookie
from the application itself, without cookie injection. Both modes asserted
HttpOnly, Strict SameSite, exact localhost host, root path and matching Secure
setting, plus expiration response attributes. The first harness attempt used
Playwright's filtered response headers and could not inspect Set-Cookie; using
`allHeaders()` fixed the harness before both successful runs.

The harness uses only its local synthetic HTTP upstream on 127.0.0.1:8130 and
Next on 127.0.0.1:3130, refuses occupied ports, closes its servers/browser, and
restricts browser traffic to localhost:3130. It borrows an existing Playwright
installation read-only; no dependencies were installed or edited. A local
Playwright installation can alternatively resolve normally without the override.
No database, real provider or email is involved. Protected ports 3000/8000/8001
were untouched. Generated Next AGENTS/next-env changes were restored.

This is Chromium's localhost secure-context exception over HTTP, not staging TLS
evidence or a full authenticated backend/provider journey. Hosted HTTPS, real
provider login/logout/revocation, UI session recovery and full 7A remain open
acceptance gates.
