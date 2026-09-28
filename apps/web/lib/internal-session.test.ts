import { afterEach, describe, expect, it } from "vitest";

import { internalApiUrl, isTrustedMutationRequest } from "./internal-session";

const ORIGINAL_API_BASE_URL = process.env.API_BASE_URL;

afterEach(() => {
  if (ORIGINAL_API_BASE_URL === undefined) delete process.env.API_BASE_URL;
  else process.env.API_BASE_URL = ORIGINAL_API_BASE_URL;
});

describe("internal session server helpers", () => {
  it("uses the configured API origin when present", () => {
    process.env.API_BASE_URL = "https://api.internal.example/root";
    expect(String(internalApiUrl("/v1/auth/me"))).toBe(
      "https://api.internal.example/v1/auth/me",
    );
  });

  it("allows safe requests and rejects mutations without browser provenance", () => {
    expect(
      isTrustedMutationRequest(
        new Request("http://web.test/api/internal/roles", { method: "GET" }),
      ),
    ).toBe(true);
    expect(
      isTrustedMutationRequest(
        new Request("http://web.test/api/internal/roles", { method: "POST" }),
      ),
    ).toBe(false);
  });

  it("recognizes the actual HTTP host when Next normalizes a loopback URL", () => {
    expect(
      isTrustedMutationRequest(
        new Request("http://localhost:3000/api/session", {
          method: "POST",
          headers: { Host: "127.0.0.1:3000", Origin: "http://127.0.0.1:3000" },
        }),
      ),
    ).toBe(true);
    expect(
      isTrustedMutationRequest(
        new Request("http://localhost:3000/api/session", {
          method: "POST",
          headers: {
            Host: "localhost:3000",
            Origin: "https://attacker.example",
            "X-Forwarded-Host": "attacker.example",
          },
        }),
      ),
    ).toBe(false);
  });
});
