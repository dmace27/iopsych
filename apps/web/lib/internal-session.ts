/** Shared server-only settings for the internal-user browser session. */
export const INTERNAL_SESSION_COOKIE = "iopsych_internal_token";

/** Build an upstream API URL from the server-only configured origin. */
export function internalApiUrl(path: string): URL {
  return new URL(path, process.env.API_BASE_URL ?? "http://localhost:8000");
}

/**
 * Require browser mutation requests to originate from this web application.
 *
 * An Origin header is preferred. Fetch Metadata provides a safe fallback for
 * browsers that omit Origin, while non-browser callers must supply one of the
 * two signals explicitly.
 */
export function isTrustedMutationRequest(request: Request): boolean {
  if (["GET", "HEAD", "OPTIONS"].includes(request.method)) return true;

  const origin = request.headers.get("origin");
  if (origin !== null) return origin === new URL(request.url).origin;
  return request.headers.get("sec-fetch-site") === "same-origin";
}
