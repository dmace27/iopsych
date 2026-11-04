# Runtime and retained-version boundary review

Reviewed revision: `c78a70c` on `AbhiNutakki/iopsych-boundary-review`,
2026-11-04. Read-only application review; this document is the sole changed
file. Read the final implementation plan, progress ledger, relevant
implementation reports and web AGENTS guidance. No app code, dependency,
migration, shared contract, live service, existing database or other worker's
uncommitted changes were modified.

## Finding: extraction redirects forward the provider credential

**P1 — fix before configured-provider use.** Owner:
`apps/api/app/extraction/provider.py:100–114`; regression ownership:
`apps/api/tests/test_extraction_bounds.py`.

The adapter supplies Authorization to standard `urllib.request.urlopen`, whose
default redirect handler forwards that header when an HTTPS POST receives a 302
to a different HTTP origin. The base-URL HTTPS validation only checks the first
URL. A redirecting configured endpoint can therefore disclose the credential to
another origin, including over plaintext HTTP. This is an existing transport
behavior exposed by this review, not a claim that the new byte limits introduced
it. Exploitation requires a redirect response from the configured provider or
its serving infrastructure; ordinary candidate input alone does not control it.

A network-free probe exercised the actual adapter and standard redirect handler,
replacing only transport with synthetic responses. It observed exactly:

```text
[('http://capture.invalid/redirected', 'GET', 'Bearer synthetic-only')]
```

No real credential or external network was used. The POST body was dropped by
the 302 handling in this reproduction; credential disclosure alone is proven.
Reject redirects before a follow-up request, or enforce an explicit approved
same-origin HTTPS policy without forwarding credentials elsewhere. Rejected
redirects should become terminal safe provider errors. Add downgrade and
cross-origin tests through the real redirect mechanism, not only mocked
`urlopen` exceptions.

Reported immediately to coordinator in `msg_7c39f302e9ab`; coordinator accepted
and assigned a separate redirect-fix worker in `msg_efa7740b08cb`. This review
does not claim the subsequent fix has been implemented or validated.

### Exact reproduction

From repository root, run the following. All HTTP/HTTPS transport is
intercepted; `.invalid` URLs are labels only. The synthetic key is intentionally
not secret.

```sh
PYTHONPATH=apps/api:packages/shared/python .venv/bin/python - <<'PY'
import json
from email.message import Message
from io import BytesIO
from unittest.mock import patch
from urllib.request import HTTPSHandler, HTTPHandler, build_opener
from urllib.response import addinfourl
from pydantic import SecretStr
from app.extraction.config import RoleExtractionSettings
from app.extraction.provider import OpenAIStructuredRoleExtractionProvider, RoleExtractionInput

seen = []

class SyntheticTransport(HTTPSHandler, HTTPHandler):
    def https_open(self, req):
        headers = Message()
        headers['Location'] = 'http://capture.invalid/redirected'
        response = addinfourl(BytesIO(b''), headers, req.full_url, 302)
        response.msg = 'Found'
        return response

    def http_open(self, req):
        seen.append((req.full_url, req.get_method(), req.get_header('Authorization')))
        body = json.dumps({'output': [{'type': 'message', 'content': [
            {'type': 'output_text', 'text': '{}'}
        ]}]}).encode()
        response = addinfourl(BytesIO(body), Message(), req.full_url, 200)
        response.msg = 'OK'
        return response

opener = build_opener(SyntheticTransport())
settings = RoleExtractionSettings(_env_file=None, api_key=SecretStr('synthetic-only'))
with patch('app.extraction.provider.urlopen', opener.open):
    OpenAIStructuredRoleExtractionProvider(settings).extract(
        RoleExtractionInput('Synthetic', 'Test', 'Local', 'Synthetic job')
    )
assert seen == [('http://capture.invalid/redirected', 'GET', 'Bearer synthetic-only')]
print(seen)
PY
```

Result at reviewed revision: exit 0; assertion confirmed. A fixed implementation
should reject the redirect and never enter `http_open`.

## Other scoped review results

| Boundary                | Review / independently executed evidence                                                        | Result                                                                                                                                                                          |
| ----------------------- | ----------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 6C retained snapshot    | Actual registry probe changed title and recomputed hash, then called `read_assignment`          | Rejected with `unsupported_assessment_version`; exact retained checksum is enforced independently of stored checksum consistency                                                |
| Frontend hash parity    | Node probe applied the frontend recursive canonicalization to backend retained JSON             | SHA-256 equals `021233ca4dab9c86b87aeabca88f503bf7c70fd0b0d324c64e788b620aeb6e3c`                                                                                               |
| Retirement              | Read `new_assignment`, `read_assignment`, scoring/matching/report consumers and integrity tests | Issuance policy is separate from immutable content; historical readers do not reject solely because of retirement policy                                                        |
| Request body rejection  | Called actual ASGI middleware with five bytes and a four-byte configured cap                    | 413 before app invocation; response contains no synthetic token from the path                                                                                                   |
| Extraction limits       | Read provider/service and focused tests                                                         | Bounded response read, UTF-8 output limit, shrinking retry budget, terminal size errors and admission cleanup are present; hard cancellation is explicitly not promised         |
| Local SMTP privacy      | Injected transport `OSError` containing synthetic private text into actual adapter              | Safe `InvitationDeliveryError`; formatted traceback omits private transport text                                                                                                |
| Local SMTP restrictions | Read construction and send paths                                                                | Explicit opt-in, numeric loopback, reserved synthetic recipient suffixes, finite socket timeout and no automatic installation; relay-free sink remains an operator prerequisite |
| Sign-out                | Read integrated route, shared cookie helper, focused unit/browser evidence                      | Expiration now uses the same Secure/HttpOnly/root-path/SameSite attributes as creation, including production `__Host-` cookie; no new defect found                              |

These were small in-memory probes, not another broad test run. The hash probe
copies the client canonicalization algorithm; it does not claim to execute the
browser client itself. Sign-out browser results in the prior report were read,
not rerun. No server, SMTP sink, browser, provider, container or PostgreSQL
instance was started. All reserved/protected ports, including 8136, remained
unused. No full suite or package acceptance is claimed.

## Active-worker contracts and remaining work

The committed `/ready` contract is DB connectivity only, with a safe 503 on
SQLAlchemy failure and independent `/health` liveness. The dynamic-readiness
worker owns deadlines/schema evolution; this review did not inspect or change
its uncommitted implementation. Preserve the current no-provider-call and
redacted-response contract when adding database/schema checks.

For the separate telemetry worker, body-limit rejections happen outside audit
and routing, inside security middleware. Correlation/measurement wrapping must
cover 408/413 and outer unexpected-error responses without recording candidate
path tokens, Authorization, request bodies, SMTP replies, exception locals, or
provider error payloads. This is integration contract review, not evidence that
uncommitted telemetry satisfies it.

Next action is the assigned redirect repair and its focused regression check.
Existing documented limitations (hard extraction cancellation, process-local
admission, readiness deadlines, hosted validation and scientific/product gates)
remain with their respective owners and are not refiled as new bugs here.
