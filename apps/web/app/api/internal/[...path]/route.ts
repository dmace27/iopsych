import { cookies } from "next/headers";

import {
  INTERNAL_SESSION_COOKIE,
  internalApiUrl,
  isTrustedMutationRequest,
} from "../../../../lib/internal-session";

interface RouteContext {
  params: Promise<{ path: string[] }>;
}

/** Limit the credential-bearing proxy to implemented internal endpoints. */
function isAllowedInternalPath(path: string[], method: string): boolean {
  return (
    path[0] === "roles" ||
    (path[0] === "reports" &&
      ((method === "POST" && path.length === 1) ||
        (method === "GET" && path.length === 2))) ||
    (path.length === 2 && path[0] === "auth" && path[1] === "me")
  );
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
  if (!isAllowedInternalPath(path, request.method)) {
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

  try {
    const upstream = await fetch(upstreamUrl, {
      method: request.method,
      headers,
      body: body.byteLength > 0 ? body : undefined,
      cache: "no-store",
    });
    if (upstream.status === 204) {
      return new Response(null, { status: 204 });
    }
    return new Response(await upstream.arrayBuffer(), {
      status: upstream.status,
      headers: {
        "Cache-Control": "no-store",
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
