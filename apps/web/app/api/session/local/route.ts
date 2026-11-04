import { cookies } from "next/headers";

import {
  INTERNAL_SESSION_COOKIE,
  internalApiUrl,
  isTrustedMutationRequest,
} from "../../../../lib/internal-session";

const LOOPBACK = new Set(["localhost", "127.0.0.1", "[::1]"]);

function hasLoopbackHost(request: Request): boolean {
  // Next may normalize request.url to its listener. Validate the actual HTTP
  // authority separately, without URL coercions or forwarded-host headers.
  const host = request.headers.get("host");
  if (!host) return false;
  const authority =
    /^(localhost|127\.0\.0\.1|\[::1\])(?::([0-9]{1,5}))?$/i.exec(host);
  if (!authority) return false;
  return (
    authority[2] === undefined ||
    (Number(authority[2]) > 0 && Number(authority[2]) <= 65535)
  );
}

/** Exchange fixed synthetic identities without exposing a token to browser JS. */
export async function POST(request: Request): Promise<Response> {
  const headers = { "Cache-Control": "no-store" };
  const upstreamUrl = internalApiUrl("/v1/auth/local-login");
  const localUrl = new URL(request.url);
  if (
    process.env.LOCAL_LOGIN_ENABLED !== "true" ||
    process.env.NODE_ENV !== "development" ||
    !hasLoopbackHost(request) ||
    !LOOPBACK.has(localUrl.hostname) ||
    localUrl.protocol !== "http:" ||
    !LOOPBACK.has(upstreamUrl.hostname) ||
    upstreamUrl.protocol !== "http:"
  ) {
    return Response.json(
      { detail: "Local login is unavailable." },
      { status: 404, headers },
    );
  }
  if (!isTrustedMutationRequest(request)) {
    return Response.json(
      { detail: "Same-origin request required." },
      { status: 403, headers },
    );
  }
  const body: unknown = await request.json().catch(() => null);
  if (
    !body ||
    typeof body !== "object" ||
    !("identity" in body) ||
    !["alpha", "beacon"].includes(String(body.identity)) ||
    Object.keys(body).length !== 1
  ) {
    return Response.json(
      { detail: "Select a synthetic identity." },
      { status: 400, headers },
    );
  }
  try {
    const upstream = await fetch(upstreamUrl, {
      method: "POST",
      cache: "no-store",
      signal: AbortSignal.timeout(5000),
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!upstream.ok) {
      return Response.json(
        {
          detail:
            "Local login unavailable; check API policy and synthetic seed.",
        },
        { status: 503, headers },
      );
    }
    const payload: unknown = await upstream.json();
    if (
      !payload ||
      typeof payload !== "object" ||
      !("access_token" in payload) ||
      typeof payload.access_token !== "string" ||
      !payload.access_token ||
      payload.access_token.length > 16384
    ) {
      return Response.json(
        { detail: "Invalid local login response." },
        { status: 502, headers },
      );
    }
    (await cookies()).set(INTERNAL_SESSION_COOKIE, payload.access_token, {
      httpOnly: true,
      maxAge: 900,
      path: "/",
      sameSite: "strict",
      secure: false,
    });
    return Response.json({ status: "ok" }, { headers });
  } catch {
    return Response.json(
      { detail: "Local API is unavailable." },
      { status: 502, headers },
    );
  }
}
