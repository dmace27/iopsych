import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const headerMocks = vi.hoisted(() => ({
  cookieGet: vi.fn(),
  cookies: vi.fn(),
}));

vi.mock("next/headers", () => ({ cookies: headerMocks.cookies }));

import { DELETE, GET, PATCH, POST } from "./route";

const ORIGINAL_API_BASE_URL = process.env.API_BASE_URL;

/** Build the shape supplied to a Next catch-all route without a Next runtime. */
function context(...path: string[]) {
  return { params: Promise.resolve({ path }) };
}

describe("internal API proxy", () => {
  beforeEach(() => {
    headerMocks.cookieGet.mockReset();
    headerMocks.cookies.mockReset();
    headerMocks.cookies.mockResolvedValue({ get: headerMocks.cookieGet });
    delete process.env.API_BASE_URL;
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    if (ORIGINAL_API_BASE_URL === undefined) delete process.env.API_BASE_URL;
    else process.env.API_BASE_URL = ORIGINAL_API_BASE_URL;
  });

  it("rejects a cross-site state-changing request before reading credentials", async () => {
    const response = await POST(
      new Request("http://web.test/api/internal/roles", {
        headers: { Origin: "https://attacker.example" },
        method: "POST",
      }),
      context("roles"),
    );

    expect(response.status).toBe(403);
    await expect(response.json()).resolves.toMatchObject({
      code: "cross_site_request_denied",
    });
    expect(headerMocks.cookies).not.toHaveBeenCalled();
  });

  it("rejects a request when neither session credential is configured", async () => {
    headerMocks.cookieGet.mockReturnValue(undefined);

    const response = await GET(
      new Request("http://web.test/api/internal/roles"),
      context("roles"),
    );

    expect(response.status).toBe(401);
    await expect(response.json()).resolves.toMatchObject({
      code: "authentication_required",
      status: 401,
    });
    expect(fetch).not.toHaveBeenCalled();
  });

  it("does not forward endpoints outside the internal role workflow", async () => {
    headerMocks.cookieGet.mockReturnValue({ value: "cookie-token" });

    const response = await GET(
      new Request("http://web.test/api/internal/candidates"),
      context("candidates"),
    );

    expect(response.status).toBe(404);
    await expect(response.json()).resolves.toMatchObject({
      code: "route_not_found",
      status: 404,
    });
    expect(fetch).not.toHaveBeenCalled();
  });

  it("forwards the exact current-user endpoint", async () => {
    headerMocks.cookieGet.mockReturnValue({ value: "cookie-token" });
    vi.mocked(fetch).mockResolvedValue(
      Response.json({ role: "recruiter" }, { status: 200 }),
    );

    const response = await GET(
      new Request("http://web.test/api/internal/auth/me"),
      context("auth", "me"),
    );

    expect(response.status).toBe(200);
    expect(fetch).toHaveBeenCalledWith(
      new URL("http://localhost:8000/v1/auth/me"),
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("forwards a cookie-authenticated GET and encodes path segments", async () => {
    headerMocks.cookieGet.mockReturnValue({ value: "cookie-token" });
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify({ id: "role-response" }), {
        headers: { "Content-Type": "application/json; charset=utf-8" },
        status: 200,
      }),
    );

    const response = await GET(
      new Request("http://web.test/api/internal/roles/a%2Fb"),
      context("roles", "a/b"),
    );

    expect(fetch).toHaveBeenCalledOnce();
    const [url, init] = vi.mocked(fetch).mock.calls[0]!;
    expect(String(url)).toBe("http://localhost:8000/v1/roles/a%2Fb");
    expect(init).toMatchObject({ cache: "no-store", method: "GET" });
    expect(new Headers(init?.headers).get("Authorization")).toBe(
      "Bearer cookie-token",
    );
    expect(init?.body).toBeUndefined();
    expect(response.headers.get("Content-Type")).toBe(
      "application/json; charset=utf-8",
    );
    await expect(response.json()).resolves.toEqual({ id: "role-response" });
  });

  it("forwards a same-origin cookie-authenticated JSON POST body", async () => {
    headerMocks.cookieGet.mockReturnValue({ value: "cookie-token" });
    process.env.API_BASE_URL = "https://api.internal.example/base";
    const upstream = new Response(JSON.stringify({ created: true }), {
      status: 201,
    });
    upstream.headers.delete("Content-Type");
    vi.mocked(fetch).mockResolvedValue(upstream);
    const request = new Request("http://web.test/api/internal/roles", {
      body: JSON.stringify({ title: "Engineer" }),
      headers: {
        "Content-Type": "application/json",
        Origin: "http://web.test",
      },
      method: "POST",
    });

    const response = await POST(request, context("roles"));

    const [url, init] = vi.mocked(fetch).mock.calls[0]!;
    expect(String(url)).toBe("https://api.internal.example/v1/roles");
    expect(init?.method).toBe("POST");
    expect(new Headers(init?.headers).get("Authorization")).toBe(
      "Bearer cookie-token",
    );
    expect(new Headers(init?.headers).get("Content-Type")).toBe(
      "application/json",
    );
    expect(new TextDecoder().decode(init?.body as ArrayBuffer)).toBe(
      JSON.stringify({ title: "Engineer" }),
    );
    expect(response.status).toBe(201);
    expect(response.headers.get("Content-Type")).toBe("application/json");
  });

  it("omits a content type when a PATCH body has no declared media type", async () => {
    headerMocks.cookieGet.mockReturnValue({ value: "cookie-token" });
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify({ revised: true }), { status: 200 }),
    );
    const request = new Request("http://web.test/api/internal/roles/1", {
      headers: {
        "Content-Type": "application/json",
        "Sec-Fetch-Site": "same-origin",
      },
      method: "PATCH",
    });

    await PATCH(request, context("roles", "1"));

    const [, init] = vi.mocked(fetch).mock.calls[0]!;
    expect(new Headers(init?.headers).has("Content-Type")).toBe(false);
  });

  it("returns an empty response for an upstream DELETE", async () => {
    headerMocks.cookieGet.mockReturnValue({ value: "cookie-token" });
    vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 204 }));

    const response = await DELETE(
      new Request("http://web.test/api/internal/roles/1", {
        headers: { Origin: "http://web.test" },
        method: "DELETE",
      }),
      context("roles", "1"),
    );

    expect(response.status).toBe(204);
    await expect(response.text()).resolves.toBe("");
  });

  it("returns a stable problem when the upstream API cannot be reached", async () => {
    headerMocks.cookieGet.mockReturnValue({ value: "cookie-token" });
    vi.mocked(fetch).mockRejectedValue(new Error("private network detail"));

    const response = await GET(
      new Request("http://web.test/api/internal/roles"),
      context("roles"),
    );

    expect(response.status).toBe(502);
    await expect(response.json()).resolves.toEqual({
      code: "api_unavailable",
      detail: "The internal API could not be reached. Try again shortly.",
      status: 502,
      title: "API unavailable",
      type: "about:blank",
    });
  });

  it("forwards report reads and same-origin generation through the session cookie", async () => {
    headerMocks.cookieGet.mockReturnValue({ value: "cookie-token" });
    vi.mocked(fetch).mockImplementation(async () =>
      Response.json({ id: "report" }),
    );
    await GET(
      new Request("http://web.test/api/internal/reports/report-id"),
      context("reports", "report-id"),
    );
    expect(fetch).toHaveBeenLastCalledWith(
      new URL("http://localhost:8000/v1/reports/report-id"),
      expect.objectContaining({ method: "GET" }),
    );
    const response = await POST(
      new Request("http://web.test/api/internal/reports", {
        method: "POST",
        headers: {
          Origin: "http://web.test",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          assessment_id: "assessment",
          role_profile_id: "profile",
        }),
      }),
      context("reports"),
    );
    expect(response.headers.get("Cache-Control")).toBe("no-store");
    expect(fetch).toHaveBeenLastCalledWith(
      new URL("http://localhost:8000/v1/reports"),
      expect.objectContaining({ method: "POST" }),
    );
    const [, init] = vi.mocked(fetch).mock.calls.at(-1)!;
    expect(new Headers(init?.headers).get("Authorization")).toBe(
      "Bearer cookie-token",
    );
  });

  it("rejects report mutation and cross-site generation without forwarding credentials", async () => {
    headerMocks.cookieGet.mockReturnValue({ value: "cookie-token" });
    for (const handler of [PATCH, DELETE]) {
      const response = await handler(
        new Request("http://web.test/api/internal/reports/report-id", {
          method: handler === PATCH ? "PATCH" : "DELETE",
          headers: { Origin: "http://web.test" },
        }),
        context("reports", "report-id"),
      );
      expect(response.status).toBe(404);
    }
    const response = await POST(
      new Request("http://web.test/api/internal/reports", {
        method: "POST",
        headers: { Origin: "https://attacker.example" },
      }),
      context("reports"),
    );
    expect(response.status).toBe(403);
    expect(fetch).not.toHaveBeenCalled();
  });

  it("preserves assessment discovery pagination", async () => {
    headerMocks.cookieGet.mockReturnValue({ value: "cookie-token" });
    vi.mocked(fetch).mockResolvedValue(Response.json([]));
    await GET(
      new Request(
        "http://web.test/api/internal/roles/role-id/assessments?offset=50&limit=10",
      ),
      context("roles", "role-id", "assessments"),
    );
    expect(String(vi.mocked(fetch).mock.calls[0]![0])).toBe(
      "http://localhost:8000/v1/roles/role-id/assessments?offset=50&limit=10",
    );
  });
});
