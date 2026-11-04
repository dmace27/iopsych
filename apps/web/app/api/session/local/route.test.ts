import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const cookieMocks = vi.hoisted(() => ({ set: vi.fn() }));
vi.mock("next/headers", () => ({ cookies: async () => cookieMocks }));
import { POST } from "./route";

function request(
  body: unknown = { identity: "alpha" },
  url = "http://127.0.0.1:3101/api/session/local",
  origin = "http://127.0.0.1:3101",
) {
  return new Request(url, {
    method: "POST",
    body: JSON.stringify(body),
    headers: { Origin: origin },
  });
}

describe("local synthetic session", () => {
  beforeEach(() => {
    vi.stubEnv("LOCAL_LOGIN_ENABLED", "true");
    vi.stubEnv("NODE_ENV", "development");
    vi.stubEnv("API_BASE_URL", "http://127.0.0.1:8101");
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(Response.json({ access_token: "synthetic-token" })),
    );
    cookieMocks.set.mockReset();
  });
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });
  it.each([
    ["LOCAL_LOGIN_ENABLED", "false"],
    ["NODE_ENV", "production"],
    ["API_BASE_URL", "http://hosted.example"],
    ["API_BASE_URL", "https://localhost"],
  ])("fails closed for %s=%s", async (name, value) => {
    vi.stubEnv(name, value);
    expect((await POST(request())).status).toBe(404);
    expect(fetch).not.toHaveBeenCalled();
  });
  it.each([
    "http://hosted.example/api/session/local",
    "https://localhost/api/session/local",
  ])("rejects hosted URL %s", async (url) => {
    expect((await POST(request({}, url))).status).toBe(404);
  });
  it("rejects cross-origin mutation", async () => {
    expect(
      (await POST(request({}, undefined, "https://attacker.example"))).status,
    ).toBe(403);
    expect(fetch).not.toHaveBeenCalled();
  });
  it.each([
    null,
    "alpha",
    {},
    { identity: "admin" },
    { identity: "alpha", role: "admin" },
  ])("rejects malformed identity %j", async (body) => {
    expect((await POST(request(body))).status).toBe(400);
  });
  it("rejects invalid JSON", async () => {
    const req = request();
    vi.spyOn(req, "json").mockRejectedValue(new Error("invalid"));
    expect((await POST(req)).status).toBe(400);
  });
  it("stores token only in short-lived HTTP-only strict cookie", async () => {
    const response = await POST(request());
    expect(await response.json()).toEqual({ status: "ok" });
    expect(response.headers.get("cache-control")).toBe("no-store");
    expect(cookieMocks.set).toHaveBeenCalledWith(
      expect.any(String),
      "synthetic-token",
      {
        httpOnly: true,
        maxAge: 900,
        path: "/",
        sameSite: "strict",
        secure: false,
      },
    );
  });
  it("handles API denial", async () => {
    vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 404 }));
    expect((await POST(request())).status).toBe(503);
    expect(cookieMocks.set).not.toHaveBeenCalled();
  });
  it.each([
    null,
    "token",
    {},
    { access_token: 1 },
    { access_token: "" },
    { access_token: "x".repeat(16385) },
  ])("rejects malformed API response %#", async (body) => {
    vi.mocked(fetch).mockResolvedValue(Response.json(body));
    expect((await POST(request())).status).toBe(502);
    expect(cookieMocks.set).not.toHaveBeenCalled();
  });
  it("handles transport failure", async () => {
    vi.mocked(fetch).mockRejectedValue(new Error("offline"));
    expect((await POST(request())).status).toBe(502);
  });
});
