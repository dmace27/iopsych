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
    headers: { Origin: origin, Host: new URL(url).host },
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
  it.each(["origin", "fetch-metadata"])(
    "rejects hostile actual Host despite normalized loopback URL and %s",
    async (signal) => {
      const req = request();
      req.headers.set("host", "rebind.example.invalid:3113");
      req.headers.set("x-forwarded-host", "127.0.0.1:3113");
      req.headers.set("forwarded", "host=127.0.0.1:3113");
      if (signal === "origin") {
        req.headers.set("origin", "http://rebind.example.invalid:3113");
      } else {
        req.headers.delete("origin");
        req.headers.set("sec-fetch-site", "same-origin");
      }
      expect((await POST(req)).status).toBe(404);
      expect(fetch).not.toHaveBeenCalled();
      expect(cookieMocks.set).not.toHaveBeenCalled();
    },
  );
  it.each([
    null,
    "",
    "localhost:",
    "localhost:0",
    "localhost:65536",
    "localhost:abc",
    "localhost:3113:80",
    "localhost,evil.invalid",
    "evil.invalid@localhost",
    "localhost@evil.invalid",
    "localhost/evil",
    "localhost?evil",
    "localhost#evil",
    "localhost\\evil",
    "local host",
    "localhost.",
    "127.1",
    "2130706433",
    "0x7f000001",
    "%6cocalhost",
    "::1",
    "[::1",
    "[::1]:-1",
    "[::ffff:127.0.0.1]",
  ])("rejects absent or malformed actual Host %s", async (host) => {
    const req = request();
    if (host === null) req.headers.delete("host");
    else req.headers.set("host", host);
    req.headers.delete("origin");
    req.headers.set("sec-fetch-site", "same-origin");
    req.headers.set("x-forwarded-host", "localhost:3101");
    expect((await POST(req)).status).toBe(404);
    expect(fetch).not.toHaveBeenCalled();
    expect(cookieMocks.set).not.toHaveBeenCalled();
  });
  it.each(["localhost", "LOCALHOST:3113", "127.0.0.1:3113", "[::1]:3113"])(
    "accepts explicit loopback authority %s with Fetch Metadata",
    async (host) => {
      const req = request();
      req.headers.set("host", host);
      req.headers.delete("origin");
      req.headers.set("sec-fetch-site", "same-origin");
      expect((await POST(req)).status).toBe(200);
      expect(fetch).toHaveBeenCalledOnce();
      expect(cookieMocks.set).toHaveBeenCalledOnce();
    },
  );
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
