import { cookies } from "next/headers";

import {
  INTERNAL_SESSION_COOKIE,
  internalApiUrl,
  isTrustedMutationRequest,
} from "../../../../lib/internal-session";

interface RouteContext {
  params: Promise<{ path: string[] }>;
}

const INVITATION_ISSUANCE_ROUTE =
  /^POST \/roles\/[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\/invites$/i;

const ALLOWED_INTERNAL_ROUTES = [
  INVITATION_ISSUANCE_ROUTE,
  /^GET \/accounts\/users$/,
  /^PATCH \/accounts\/users\/[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i,
  /^GET \/auth\/me$/,
  /^(?:GET|POST) \/roles$/,
  /^(?:GET|PATCH|DELETE) \/roles\/[^/]+$/,
  /^(?:GET|POST) \/roles\/[^/]+\/profiles$/,
  /^POST \/roles\/[^/]+\/extract-profile$/,
  /^GET \/roles\/[^/]+\/assessments$/,
  /^GET \/roles\/[^/]+\/invites$/,
  /^POST \/roles\/[^/]+\/invites\/[^/]+\/revoke$/,
  /^(?:GET|PATCH) \/roles\/[^/]+\/profiles\/[^/]+$/,
  /^POST \/roles\/[^/]+\/profiles\/[^/]+\/approve$/,
  /^POST \/reports$/,
  /^GET \/reports\/[^/]+$/,
  /^GET \/reports\/[^/]+\/trace$/,
  /^POST \/candidates\/[^/]+\/export$/,
  /^DELETE \/candidates\/[^/]+$/,
  /^GET \/privacy\/(?:status|audit-events|assessments)$/,
  /^POST \/privacy\/retention\/run$/,
];

/** Limit the credential-bearing proxy to implemented internal endpoints. */
function isAllowedInternalPath(path: string[], method: string): boolean {
  const encodedPath = path
    .map((segment) => encodeURIComponent(segment))
    .join("/");
  const route = `${method} /${encodedPath}`;
  return ALLOWED_INTERNAL_ROUTES.some((pattern) => pattern.test(route));
}

/** Build a problem response without exposing upstream or credential details. */
function problem(
  status: number,
  code: string,
  title: string,
  detail: string,
): Response {
  return Response.json(
    { type: "about:blank", title, status, detail, code },
    {
      status,
      headers: {
        "Content-Type": "application/problem+json",
        "Cache-Control": "no-store",
      },
    },
  );
}

/** Resolve the per-browser token stored only in the HTTP-only session cookie. */
async function getBearerToken(): Promise<string | undefined> {
  return (await cookies()).get(INTERNAL_SESSION_COOKIE)?.value;
}

/** Forward one same-origin request to the unchanged FastAPI `/v1` surface. */
async function proxyInternalApi(
  request: Request,
  context: RouteContext,
): Promise<Response> {
  const { path } = await context.params;
  if (
    path.some((segment) => segment === "." || segment === "..") ||
    !isAllowedInternalPath(path, request.method)
  ) {
    return problem(
      404,
      "route_not_found",
      "Route not found",
      "This internal API route is not available.",
    );
  }

  if (!isTrustedMutationRequest(request)) {
    return problem(
      403,
      "cross_site_request_denied",
      "Cross-site request denied",
      "State-changing requests must originate from this application.",
    );
  }

  const token = await getBearerToken();
  if (!token) {
    return problem(
      401,
      "authentication_required",
      "Authentication required",
      "Sign in to access the internal workspace.",
    );
  }

  const upstreamUrl = internalApiUrl(
    `/v1/${path.map((segment) => encodeURIComponent(segment)).join("/")}`,
  );
  upstreamUrl.search = new URL(request.url).search;
  const body = await request.arrayBuffer();
  const headers = new Headers({
    Accept: "application/json",
    Authorization: `Bearer ${token}`,
  });
  const contentType = request.headers.get("content-type");
  if (contentType && body.byteLength > 0) {
    headers.set("Content-Type", contentType);
  }
  if (INVITATION_ISSUANCE_ROUTE.test(`${request.method} /${path.join("/")}`)) {
    const idempotencyKey = request.headers.get("Idempotency-Key");
    // Match the API contract without rewriting the caller's retry identity.
    // Missing-key policy and strict invitation body validation belong to API.
    if (idempotencyKey !== null) {
      if (!/^[!-~]{16,128}$/.test(idempotencyKey)) {
        return problem(
          422,
          "invalid_idempotency_key",
          "Invalid idempotency key",
          "Idempotency-Key must contain 16-128 visible ASCII characters.",
        );
      }
      headers.set("Idempotency-Key", idempotencyKey);
    }
  }

  try {
    const upstream = await fetch(upstreamUrl, {
      method: request.method,
      headers,
      body: body.byteLength > 0 ? body : undefined,
      cache: "no-store",
    });
    if (upstream.status === 204) {
      return new Response(null, {
        status: 204,
        headers: { "Cache-Control": "no-store" },
      });
    }
    return new Response(await upstream.arrayBuffer(), {
      status: upstream.status,
      headers: {
        "Cache-Control": "no-store",
        ...(upstream.headers.has("Retry-After")
          ? { "Retry-After": upstream.headers.get("Retry-After")! }
          : {}),
        "Content-Type":
          upstream.headers.get("content-type") ?? "application/json",
      },
    });
  } catch {
    return problem(
      502,
      "api_unavailable",
      "API unavailable",
      "The internal API could not be reached. Try again shortly.",
    );
  }
}

/** Forward role/profile reads. */
export function GET(
  request: Request,
  context: RouteContext,
): Promise<Response> {
  return proxyInternalApi(request, context);
}

/** Forward role/profile creates and approval actions. */
export function POST(
  request: Request,
  context: RouteContext,
): Promise<Response> {
  return proxyInternalApi(request, context);
}

/** Forward role and profile-version edits. */
export function PATCH(
  request: Request,
  context: RouteContext,
): Promise<Response> {
  return proxyInternalApi(request, context);
}

/** Forward recoverable role archival. */
export function DELETE(
  request: Request,
  context: RouteContext,
): Promise<Response> {
  return proxyInternalApi(request, context);
}
