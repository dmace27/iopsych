# Package 6A review

Reviewed integrated `486c6b282682dd6b50f3cd53e263b920c0ba49cc` against parent
`16c461a`, on November 4, 2026, in the dedicated `iopsych-6a-review` worktree.
Read `docs/implementation/progress.md`, `6a-report.md`, the applicable web
`AGENTS.md`, and installed Next 16.3.8 Route Handlers and cookies documentation.
Only this report was changed. **6A acceptance should wait for the two fixes
below.**

## P1 — Nonlocal HTTP authority bypasses local session restriction

**Location:** `apps/web/app/api/session/local/route.ts:15–22`, interacting with
`apps/web/lib/internal-session.ts:27–32`.

The route checks the hostname of `request.url`, which Next constructs using its
configured listener hostname. The mutation helper separately uses the incoming
Host header for its Origin comparison. Consequently, an attacker-controlled
nonlocal Host and matching Origin pass both checks. Installed Next source
`node_modules/next/dist/server/next-server.js:1284` constructs `initURL` from
`fetchHostname` and port when those are configured.

**Reproduced through the real Next server:** started the committed web launcher
with
`LOCAL_LOGIN_ENABLED=true API_BASE_URL=http://127.0.0.1:8112 WEB_PORT=3112 npm run dev:web`.
A minimal Python HTTP server on loopback 8112 returned only
`{"access_token":"synthetic-review-placeholder"}` for POST; no database, real
JWT, or external connection was used. Sent JSON `{"identity":"alpha"}` to
`http://127.0.0.1:3112/api/session/local`:

| Host                          | Origin / Fetch Metadata                     | Result              |
| ----------------------------- | ------------------------------------------- | ------------------- |
| `127.0.0.1:3112`              | Origin `http://127.0.0.1:3112`              | 200, cookie set     |
| `rebind.example.invalid:3112` | Origin `http://rebind.example.invalid:3112` | **200, cookie set** |
| `rebind.example.invalid:3112` | No Origin; `Sec-Fetch-Site: same-origin`    | **200, cookie set** |
| `127.0.0.1:3112`              | Origin `http://evil.example.invalid`        | 403, no cookie      |

The invalid domain was only an HTTP header, never resolved. The successful body
was `{"status":"ok"}`. Cookies were checked for presence without printing
values. Both review processes were stopped afterward.

**Impact:** this defeats the explicitly promised nonloopback-host restriction.
In a DNS-rebinding scenario, where a browser permits the network transition, a
hostile origin can establish a synthetic-account cookie and use the existing
same-origin internal proxy. HttpOnly and SameSite=Strict do not prevent requests
originating on that same hostile authority. The web server calls the API over
loopback without forwarding Origin, so the API peer/host checks do not repair
this boundary. This review proves the HTTP bypass, not a complete browser DNS
rebinding exploit or bypass of browser private-network protections.

**Minimal fix:** before upstream access, require a present, strictly parsed
actual Host authority whose hostname is explicitly loopback; reject malformed or
nonlocal authorities independently of normalized `request.url`. Keep the
same-origin check and do not substitute client-supplied forwarded-host headers.
Add a regression with normalized loopback request URL plus nonlocal Host and
matching Origin, including the Fetch Metadata fallback; verify through live Next
that neither case reaches the upstream or sets a cookie. This is a 6A boundary
blocker, not deferred hosted-runtime work.

## P2 — Boolean parsing bypasses the wildcard listener guard

**Location:** `scripts/run-api.py:13–16`; API interpretation at
`apps/api/app/auth/config.py:30` (`local_login_enabled: bool`).

The launcher recognizes only case-insensitive `true`, whereas Pydantic settings
also recognize `1`, `yes`, and `on` as enabled. With any of those values and
`API_HOST=0.0.0.0`, the launcher proceeds to exec uvicorn with a wildcard
listener.

**Reproduction:** under `PYTHONPATH=apps/api .venv/bin/python`, use
`unittest.mock.patch.dict(os.environ, {"AUTH_LOCAL_LOGIN_ENABLED": value, "API_HOST": "0.0.0.0"}, clear=True)`,
mock `os.execv`, instantiate `AuthenticationSettings(_env_file=None)`, and call
`runpy.run_path("scripts/run-api.py")`. Results:

| Value            | API enabled | Launcher result             |
| ---------------- | ----------- | --------------------------- |
| `true`, `TRUE`   | true        | Refuses listener            |
| `1`, `yes`, `on` | true        | **Exec attempted**          |
| `false`          | false       | Exec attempted, as expected |

No wildcard listener was actually opened. The independent API peer restriction
still rejects ordinary remote clients, so this finding alone does not prove
remote token minting. It does violate the explicit defense against accidental
listener exposure and makes documented behavior depend on boolean spelling.

**Minimal fix:** parse the opt-in using the same boolean semantics as the API
(or consistently restrict both settings and launcher to one spelling), failing
closed on invalid values. Add parametrized launcher checks for all accepted true
spellings with wildcard and nonloopback hosts. This is in-scope 6A hardening.

## Other reviewed properties and evidence limits

- Dotenv loading uses `override=False, interpolate=False`; the shell wrapper
  resolves and quotes paths and never sources dotenv. Server arguments use
  `os.execv` with an argument array, with no shell command evaluation. Exported
  host, port and log settings are preserved. No additional execution defect was
  found in these paths.
- API opt-in defaults off, requires explicit development, loopback peer and
  actual request host, and configured local HTTP origin. Proxy headers are
  disabled by the launcher. Missing Origin is intentionally accepted for the
  server-to-server exchange; this makes the web boundary essential.
- API accepts only the fixed identity literal and forbids extra fields. User ID,
  subject, email and organization must match the exact synthetic seed;
  subsequent authentication resolves current tenant and role from storage. No
  arbitrary identity/tenant minting defect was found by inspection.
- Local JWT issuance uses configured HS256 signing, issuer/audience and a
  900-second expiry; the browser route returns status only, uses no-store and
  sets a 900-second HttpOnly, root-path, SameSite=Strict cookie. `secure: false`
  is consistent with the explicitly HTTP-only development contract. These
  protections do not mitigate the Host bypass above.
- Setup uses `npm ci`; direct Python requirements are pinned but transitive
  dependencies remain unlocked as disclosed. Compose uses a separate named
  project, loopback 5541 and project-scoped volume. That default project is
  shared by checkouts, so concurrent workers must override project/ports and
  database configuration; this reviewer started no Compose service or database.
- The coordinator had rerun the 14 launcher/login checks. This review did not
  repeat them, especially the existing launcher test's fixed 8101 port, or the
  full suites. Saved setup was not rerun: installed dependencies were available
  and the targeted probes succeeded. The original
  setup/migration/seed/full-suite results remain worker-reported evidence, not
  independently reproduced here.
- Existing unit route tests supply nonlocal `request.url` directly and omit the
  real normalized-URL/nonlocal-Host combination. Thus their passing results and
  the 6A report's claim of rejected nonloopback hosts do not establish that
  security property. Ordinary localhost HTTP rehearsal is still useful evidence
  for the happy path.
- The progress ledger at this revision still labels 6A running/commit pending;
  the coordinator should update it with integration and review/fix status.
  Package acceptance should not be inferred from the implementation report's
  statement that no blocker remains.

Hosted readiness, body/time/concurrency limits, provider integration and broader
release hardening remain deferred 11B/other package work, not additional 6A
findings. No scientific interpretation, approval policy, external provisioning,
mail, production secret, or existing worker instance was changed. Neither
finding is a claim of production exploitability with local login disabled.
Re-review of the two focused fixes is the remaining acceptance work.
