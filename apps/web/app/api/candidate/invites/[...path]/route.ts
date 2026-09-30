import {
  internalApiUrl,
  isTrustedMutationRequest,
} from "../../../../../lib/internal-session";

interface RouteContext {
  params: Promise<{ path: string[] }>;
}

/** Expose only implemented anonymous invitation and submission endpoints. */
function isAllowedCandidatePath(path: string[], method: string): boolean {
  return (
    (method === "GET" && path.length === 1) ||
    (method === "POST" &&
      path.length === 2 &&
      (path[1] === "consent" || path[1] === "submit"))
  );
}

function problem(
  status: number,
  code: string,
  title: string,
  detail: string,
): Response {
  return Response.json(
    { code, detail, status, title, type: "about:blank" },
    {
      headers: {
        "Content-Type": "application/problem+json",
        "Cache-Control": "no-store",
      },
      status,
    },
  );
}

/** Forward candidate traffic while preserving the FastAPI response contract. */
async function proxyCandidateApi(
  request: Request,
  context: RouteContext,
): Promise<Response> {
  const { path } = await context.params;
  if (
    path.some((segment) => segment === "." || segment === "..") ||
    !isAllowedCandidatePath(path, request.method)
  ) {
    return problem(
      404,
      "route_not_found",
      "Route not found",
      "This candidate API route is not available.",
    );
  }
  if (!isTrustedMutationRequest(request)) {
    return problem(
      403,
      "cross_site_request_denied",
      "Cross-site request denied",
      "Candidate requests must originate from this application.",
    );
  }

  const upstreamUrl = internalApiUrl(
    `/v1/candidate/invites/${path.map(encodeURIComponent).join("/")}`,
  );
  const body = await request.arrayBuffer();
  const headers = new Headers({ Accept: "application/json" });
  const contentType = request.headers.get("content-type");
  if (contentType && body.byteLength > 0) {
    headers.set("Content-Type", contentType);
  }

  try {
    const upstream = await fetch(upstreamUrl, {
      body: body.byteLength > 0 ? body : undefined,
      cache: "no-store",
      headers,
      method: request.method,
    });
    return new Response(await upstream.arrayBuffer(), {
      headers: {
        "Cache-Control": "no-store",
        ...(upstream.headers.has("Retry-After")
          ? { "Retry-After": upstream.headers.get("Retry-After")! }
          : {}),
        "Content-Type":
          upstream.headers.get("content-type") ?? "application/json",
      },
      status: upstream.status,
    });
  } catch {
    return problem(
      502,
      "api_unavailable",
      "Assessment service unavailable",
      "The assessment service could not be reached. Try again shortly.",
    );
  }
}

export function GET(
  request: Request,
  context: RouteContext,
): Promise<Response> {
  return proxyCandidateApi(request, context);
}

export function POST(
  request: Request,
  context: RouteContext,
): Promise<Response> {
  return proxyCandidateApi(request, context);
}
