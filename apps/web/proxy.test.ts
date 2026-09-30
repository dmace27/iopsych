import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { proxy } from "./proxy";

afterEach(() => vi.unstubAllEnvs());

describe("browser response security", () => {
  it("uses distinct script nonces and suppresses referrer and caching leaks", () => {
    vi.stubEnv("NODE_ENV", "production");
    const request = new NextRequest("https://web.test/candidate/invites/token");
    const first = proxy(request);
    const second = proxy(request);
    const policy = first.headers.get("content-security-policy")!;
    expect(policy).toContain("frame-ancestors 'none'");
    expect(policy).toContain("script-src 'self' 'nonce-");
    expect(policy).not.toContain("unsafe-eval");
    expect(policy).not.toEqual(second.headers.get("content-security-policy"));
    expect(first.headers.get("cache-control")).toBe("no-store");
    expect(
      first.headers.get("x-middleware-request-content-security-policy"),
    ).toBe(policy);
  });
  it("permits development tooling without relaxing production script policy", () => {
    vi.stubEnv("NODE_ENV", "development");
    const response = proxy(
      new NextRequest("http://localhost:3000/sign-in", {
        headers: {
          "x-nonce": "attacker",
          "Content-Security-Policy": "script-src *",
        },
      }),
    );
    expect(response.headers.get("Content-Security-Policy")).toContain(
      "unsafe-eval",
    );
    expect(response.headers.get("Content-Security-Policy")).toContain(
      "connect-src 'self' ws: wss:",
    );
    expect(response.headers.get("Content-Security-Policy")).not.toContain(
      "attacker",
    );
    expect(response.headers.get("Content-Security-Policy")).not.toContain(
      "upgrade-insecure-requests",
    );
  });
});
