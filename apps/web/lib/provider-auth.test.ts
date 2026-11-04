import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { exportJWK, generateKeyPair, SignJWT } from "jose";

const jar = vi.hoisted(() => ({
  values: new Map<string, string>(),
  set: vi.fn(),
  delete: vi.fn(),
}));
vi.mock("next/headers", () => ({
  cookies: async () => ({
    get: (name: string) =>
      jar.values.has(name) ? { value: jar.values.get(name) } : undefined,
    set: jar.set,
    delete: jar.delete,
  }),
}));

import { GET as login } from "../app/api/auth/login/route";
import { GET as callback } from "../app/api/auth/callback/route";
import { LOGIN_COOKIE } from "./provider-auth";
import { INTERNAL_SESSION_COOKIE } from "./internal-session";
import { safeReturnTo } from "./return-to";

const issuer = "https://issuer.example.invalid/";
const base = "http://localhost:3000";
let target: URL;
let mode = "ok";
let requests: string[];
const key = await generateKeyPair("RS256");
const wrongKey = await generateKeyPair("RS256");
const publicKey = {
  ...(await exportJWK(key.publicKey)),
  kid: "test",
  alg: "RS256",
  use: "sig",
};

/** Simulate the provider's actual discovery, token and JWKS HTTP contracts. */
async function providerFetch(
  input: string | URL | Request,
  init?: RequestInit,
): Promise<Response> {
  const url = input.toString();
  requests.push(url);
  if (mode === "offline") throw new Error("private provider detail");
  if (url === `${issuer}.well-known/openid-configuration`)
    return Response.json({
      issuer,
      authorization_endpoint: `${issuer}authorize`,
      token_endpoint: `${issuer}oauth/token`,
      jwks_uri: `${issuer}.well-known/jwks.json`,
      response_types_supported: ["code"],
      subject_types_supported: ["public"],
      id_token_signing_alg_values_supported: ["RS256"],
      token_endpoint_auth_methods_supported: ["client_secret_post"],
      code_challenge_methods_supported: ["S256"],
    });
  if (url === `${issuer}.well-known/jwks.json`)
    return Response.json({ keys: [publicKey] });
  if (url === `${issuer}oauth/token`) {
    const body = new URLSearchParams(String(init?.body));
    expect(body.get("code_verifier")).toBeTruthy();
    expect(body.get("redirect_uri")).toBe(`${base}/api/auth/callback`);
    const idToken = await new SignJWT({
      nonce: mode === "nonce" ? "wrong" : target.searchParams.get("nonce"),
    })
      .setProtectedHeader({ alg: "RS256", kid: "test" })
      .setIssuer(mode === "wrongIssuer" ? "https://foreign.invalid/" : issuer)
      .setAudience(mode === "wrongAudience" ? "foreign-client" : "client")
      .setSubject("auth0|recruiter")
      .setIssuedAt()
      .setExpirationTime("5m")
      .sign(mode === "signature" ? wrongKey.privateKey : key.privateKey);
    return Response.json({
      access_token:
        mode === "oversized" ? "x".repeat(4000) : "provider-api-token",
      token_type: mode === "tokenType" ? "mac" : "Bearer",
      expires_in: mode === "expiry" ? 0 : 300,
      ...(mode === "noIdToken" ? {} : { id_token: idToken }),
    });
  }
  expect(url).toBe("http://localhost:8000/v1/auth/me");
  expect(new Headers(init?.headers).get("Authorization")).toBe(
    "Bearer provider-api-token",
  );
  return Response.json(
    { role: "recruiter" },
    { status: mode === "disabled" ? 401 : mode === "apiFailure" ? 503 : 200 },
  );
}

beforeEach(() => {
  mode = "ok";
  requests = [];
  jar.values.clear();
  jar.set
    .mockReset()
    .mockImplementation((name: string, value: string) =>
      value ? jar.values.set(name, value) : jar.values.delete(name),
    );
  jar.delete
    .mockReset()
    .mockImplementation((name: string) => jar.values.delete(name));
  vi.stubEnv("AUTH0_ISSUER", issuer);
  vi.stubEnv("AUTH0_CLIENT_ID", "client");
  vi.stubEnv("AUTH0_CLIENT_SECRET", "client-secret");
  vi.stubEnv("AUTH0_AUDIENCE", "api");
  vi.stubEnv("APP_BASE_URL", base);
  vi.stubEnv("AUTH_SESSION_SECRET", "test-only-session-secret-with-32-bytes");
  vi.stubGlobal("fetch", vi.fn(providerFetch));
});
afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

async function begin(
  returnTo = "/roles/12345678-1234-4234-8234-123456789abc/reports",
) {
  const response = await login(
    new Request(`${base}/api/auth/login?${new URLSearchParams({ returnTo })}`),
  );
  target = new URL(response.headers.get("Location")!, base);
  return response;
}
function finish(state = target.searchParams.get("state")!) {
  return callback(
    new Request(
      `${base}/api/auth/callback?${new URLSearchParams({ code: "one-time-code", state })}`,
    ),
  );
}

describe("Auth0 authorization code flow", () => {
  it("uses PKCE, encrypted expiring state, signed ID tokens and API authorization", async () => {
    expect((await begin()).status).toBe(303);
    expect(target.origin).toBe("https://issuer.example.invalid");
    expect(target.searchParams.get("audience")).toBe("api");
    expect(target.searchParams.get("code_challenge_method")).toBe("S256");
    expect(target.searchParams.get("prompt")).toBe("login");
    expect(jar.values.get(LOGIN_COOKIE)).not.toContain("roles");
    expect(jar.set).toHaveBeenCalledWith(
      LOGIN_COOKIE,
      expect.any(String),
      expect.objectContaining({ httpOnly: true, sameSite: "lax", maxAge: 600 }),
    );
    const response = await finish();
    expect(response.headers.get("Location")).toBe(
      `${base}/roles/12345678-1234-4234-8234-123456789abc/reports`,
    );
    expect(response.headers.get("Cache-Control")).toBe("no-store");
    expect(jar.set).toHaveBeenCalledWith(
      INTERNAL_SESSION_COOKIE,
      "provider-api-token",
      expect.objectContaining({
        maxAge: 300,
        sameSite: "strict",
        httpOnly: true,
      }),
    );
    expect(jar.values.has(LOGIN_COOKIE)).toBe(false);
    expect(requests).toContain(`${issuer}.well-known/jwks.json`);
    // Cleared transaction prevents a normal callback replay from creating a session.
    expect((await finish()).headers.get("Location")).toBe(
      "/sign-in?error=login",
    );
    expect(jar.values.get(INTERNAL_SESSION_COOKIE)).toBe("provider-api-token");
  });

  it.each([
    "nonce",
    "signature",
    "wrongIssuer",
    "wrongAudience",
    "disabled",
    "apiFailure",
    "noIdToken",
    "oversized",
    "tokenType",
    "expiry",
    "offline",
  ])(
    "fails closed on %s without exposing provider details",
    async (failure) => {
      await begin();
      mode = failure;
      const response = await finish();
      expect(response.headers.get("Location")).toBe("/sign-in?error=login");
      expect(jar.values.has(INTERNAL_SESSION_COOKIE)).toBe(false);
      expect(jar.values.has(LOGIN_COOKIE)).toBe(false);
    },
  );

  it("rejects state mismatch, provider denial, missing or tampered transactions", async () => {
    await begin();
    expect((await finish("wrong-state")).headers.get("Location")).toContain(
      "error=login",
    );
    expect(requests).not.toContain(`${issuer}oauth/token`);
    await begin();
    expect(
      (
        await callback(
          new Request(
            `${base}/api/auth/callback?error=access_denied&state=${target.searchParams.get("state")}`,
          ),
        )
      ).headers.get("Location"),
    ).toContain("error=login");
    jar.values.set(LOGIN_COOKIE, "tampered");
    expect((await finish()).headers.get("Location")).toContain("error=login");
    expect((await finish()).headers.get("Location")).toContain("error=login");
  });

  it("expires the login transaction after ten minutes", async () => {
    await begin();
    vi.useFakeTimers();
    vi.setSystemTime(Date.now() + 601_000);
    try {
      expect((await finish()).headers.get("Location")).toContain("error=login");
    } finally {
      vi.useRealTimers();
    }
  });

  it.each([
    ["AUTH_SESSION_SECRET", "short"],
    ["AUTH0_CLIENT_ID", ""],
    ["AUTH0_ISSUER", "http://insecure.invalid"],
    ["APP_BASE_URL", "https://app.invalid/path"],
    ["APP_BASE_URL", "http://public.invalid"],
  ])("fails safely on invalid configuration %s", async (name, value) => {
    vi.stubEnv(name, value);
    const response = await begin();
    expect(response.headers.get("Location")).toBe(
      "/sign-in?error=configuration",
    );
    expect(jar.values.has(LOGIN_COOKIE)).toBe(false);
  });

  it("handles failed discovery", async () => {
    mode = "offline";
    expect((await begin()).headers.get("Location")).toContain(
      "error=configuration",
    );
  });
});

it("accepts internal return paths and rejects open redirects and auth loops", () => {
  for (const path of [
    "/roles",
    "/roles/12345678-1234-4234-8234-123456789abc/reports",
    "/roles/12345678-1234-4234-8234-123456789abc/invites",
    "/reports/12345678-1234-4234-8234-123456789abc",
    "/accounts",
    "/privacy",
  ])
    expect(safeReturnTo(path)).toBe(path);
  for (const path of [
    undefined,
    "/privacy?help=1",
    "/roles/abc/reports",
    "/candidate/invites/secret",
    "https://evil.invalid",
    "//evil.invalid",
    "/\\evil.invalid",
    "/%2f%2fevil.invalid",
    "/roles/../api/auth/login",
    "/api/auth/login",
    "/sign-in",
    "/roles\n",
    "/roles?x=\\evil",
    "x".repeat(2049),
  ])
    expect(safeReturnTo(path)).toBe("/roles");
});
