import { cookies } from "next/headers";

import {
  INTERNAL_SESSION_COOKIE,
  internalApiUrl,
  isTrustedMutationRequest,
} from "../../../lib/internal-session";

const MAX_TOKEN_LENGTH = 16_384;

/** Return a stable problem response without exposing token or upstream detail. */
function problem(
  status: number,
  code: string,
  title: string,
  detail: string,
  headers: Record<string, string> = {},
): Response {
  return Response.json(
    { type: "about:blank", title, status, detail, code },
    {
      status,
      headers: {
        "Content-Type": "application/problem+json",
        "Cache-Control": "no-store",
        ...headers,
      },
    },
  );
}

/** Validate a provider token and establish a secure browser-only session. */
export async function POST(request: Request): Promise<Response> {
  if (!isTrustedMutationRequest(request)) {
    return problem(
      403,
      "cross_site_request_denied",
      "Cross-site request denied",
      "Sign-in requests must originate from this application.",
    );
  }

  const payload: unknown = await request.json().catch(() => null);
  const token =
    typeof payload === "object" &&
    payload !== null &&
    "token" in payload &&
    typeof payload.token === "string"
      ? payload.token.trim()
      : "";
  if (!token || token.length > MAX_TOKEN_LENGTH) {
    return problem(
      400,
      "invalid_session_token",
      "Invalid session token",
      "Provide a valid internal-user access token.",
    );
  }

  let upstream: Response;
  try {
    upstream = await fetch(internalApiUrl("/v1/auth/me"), {
      cache: "no-store",
      headers: {
        Accept: "application/json",
        Authorization: `Bearer ${token}`,
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

  if (upstream.status === 429) {
    return problem(
      429,
      "rate_limit_exceeded",
      "Too many requests",
      "Too many sign-in requests were made. Try again later.",
      { "Retry-After": upstream.headers.get("Retry-After") ?? "60" },
    );
  }

  if (!upstream.ok) {
    return upstream.status >= 500
      ? problem(
          502,
          "api_unavailable",
          "API unavailable",
          "The internal API could not validate the session.",
        )
      : problem(
          401,
          "authentication_required",
          "Authentication required",
          "The access token is invalid or expired.",
        );
  }

  const cookieStore = await cookies();
  cookieStore.set(INTERNAL_SESSION_COOKIE, token, {
    httpOnly: true,
    maxAge: 8 * 60 * 60,
    path: "/",
    sameSite: "strict",
    secure: process.env.NODE_ENV === "production",
  });
  return new Response(await upstream.arrayBuffer(), {
    headers: {
      "Cache-Control": "no-store",
      "Content-Type":
        upstream.headers.get("content-type") ?? "application/json",
    },
    status: 200,
  });
}

/** Clear the browser session using the same cross-site request protection. */
export async function DELETE(request: Request): Promise<Response> {
  if (!isTrustedMutationRequest(request)) {
    return problem(
      403,
      "cross_site_request_denied",
      "Cross-site request denied",
      "Sign-out requests must originate from this application.",
    );
  }

  (await cookies()).delete(INTERNAL_SESSION_COOKIE);
  return new Response(null, {
    status: 204,
    headers: { "Cache-Control": "no-store" },
  });
}
