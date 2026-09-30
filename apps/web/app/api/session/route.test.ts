import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const cookieMocks = vi.hoisted(() => ({
  cookies: vi.fn(),
  delete: vi.fn(),
  set: vi.fn(),
}));

vi.mock("next/headers", () => ({ cookies: cookieMocks.cookies }));

import { DELETE, POST } from "./route";

const SAME_ORIGIN_HEADERS = {
  "Content-Type": "application/json",
  Origin: "http://web.test",
};

/** Build a same-origin JSON sign-in request for one candidate token value. */
function signInRequest(token: unknown): Request {
  return new Request("http://web.test/api/session", {
    body: JSON.stringify({ token }),
    headers: SAME_ORIGIN_HEADERS,
    method: "POST",
  });
}

describe("internal browser session", () => {
  beforeEach(() => {
    cookieMocks.cookies.mockReset();
    cookieMocks.delete.mockReset();
    cookieMocks.set.mockReset();
    cookieMocks.cookies.mockResolvedValue({
      delete: cookieMocks.delete,
      set: cookieMocks.set,
    });
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("rejects cross-site sign-in and sign-out requests", async () => {
    const crossSite = { Origin: "https://attacker.example" };
    const signIn = await POST(
      new Request("http://web.test/api/session", {
        headers: crossSite,
        method: "POST",
      }),
    );
    const signOut = await DELETE(
      new Request("http://web.test/api/session", {
        headers: crossSite,
        method: "DELETE",
      }),
    );

    expect(signIn.status).toBe(403);
    expect(signOut.status).toBe(403);
    expect(fetch).not.toHaveBeenCalled();
  });

  it("rejects malformed, missing, and oversized tokens", async () => {
    const malformed = await POST(
      new Request("http://web.test/api/session", {
        body: "not-json",
        headers: SAME_ORIGIN_HEADERS,
        method: "POST",
      }),
    );
    const missing = await POST(signInRequest(42));
    const oversized = await POST(signInRequest("x".repeat(16_385)));

    expect(malformed.status).toBe(400);
    expect(missing.status).toBe(400);
    expect(oversized.status).toBe(400);
    expect(fetch).not.toHaveBeenCalled();
  });

  it("validates the token and stores it with strict cookie protections", async () => {
    const user = { id: "user-id", role: "recruiter" };
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify(user), {
        headers: { "Content-Type": "application/json; charset=utf-8" },
        status: 200,
      }),
    );

    const response = await POST(signInRequest("provider-token"));

    expect(fetch).toHaveBeenCalledWith(
      new URL("http://localhost:8000/v1/auth/me"),
      expect.objectContaining({
        cache: "no-store",
        headers: expect.objectContaining({
          Authorization: "Bearer provider-token",
        }),
      }),
    );
    expect(cookieMocks.set).toHaveBeenCalledWith(
      "iopsych_internal_token",
      "provider-token",
      expect.objectContaining({
        httpOnly: true,
        maxAge: 8 * 60 * 60,
        path: "/",
        sameSite: "strict",
      }),
    );
    expect(response.status).toBe(200);
    expect(response.headers.get("Content-Type")).toBe(
      "application/json; charset=utf-8",
    );
    await expect(response.json()).resolves.toEqual(user);
  });

  it("uses a JSON response content type when the API omits one", async () => {
    const upstream = new Response(new TextEncoder().encode("{}"));
    upstream.headers.delete("Content-Type");
    vi.mocked(fetch).mockResolvedValue(upstream);

    const response = await POST(signInRequest("provider-token"));

    expect(response.headers.get("Content-Type")).toBe("application/json");
  });

  it("normalizes invalid credentials and upstream service failures", async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(new Response(null, { status: 401 }))
      .mockResolvedValueOnce(new Response(null, { status: 503 }))
      .mockRejectedValueOnce(new Error("private network detail"));

    const invalid = await POST(signInRequest("invalid-token"));
    const unavailable = await POST(signInRequest("valid-looking-token"));
    const networkFailure = await POST(signInRequest("another-token"));

    expect(invalid.status).toBe(401);
    expect(unavailable.status).toBe(502);
    expect(networkFailure.status).toBe(502);
    await expect(invalid.json()).resolves.toMatchObject({
      code: "authentication_required",
    });
    await expect(unavailable.json()).resolves.toMatchObject({
      code: "api_unavailable",
    });
  });

  it("clears a same-origin session", async () => {
    const response = await DELETE(
      new Request("http://web.test/api/session", {
        headers: { "Sec-Fetch-Site": "same-origin" },
        method: "DELETE",
      }),
    );

    expect(cookieMocks.delete).toHaveBeenCalledWith("iopsych_internal_token");
    expect(response.status).toBe(204);
  });
});

it("preserves API throttling and never creates a session on a rate-limit failure", async () => {
  cookieMocks.set.mockClear();
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValue(
        new Response(null, { status: 429, headers: { "Retry-After": "27" } }),
      ),
  );
  try {
    const response = await POST(signInRequest("provider-token"));
    expect(response.status).toBe(429);
    expect(response.headers.get("Retry-After")).toBe("27");
    expect(response.headers.get("Cache-Control")).toBe("no-store");
    expect(cookieMocks.set).not.toHaveBeenCalled();
    vi.mocked(fetch).mockResolvedValueOnce(new Response(null, { status: 429 }));
    expect(
      (await POST(signInRequest("token"))).headers.get("Retry-After"),
    ).toBe("60");
  } finally {
    vi.unstubAllGlobals();
  }
});
