/** Server-only Auth0 authorization-code flow with PKCE and encrypted state. */
import { createHash } from "node:crypto";
import { cookies } from "next/headers";
import { EncryptJWT, jwtDecrypt } from "jose";
import * as oidc from "openid-client";

import { INTERNAL_SESSION_COOKIE, internalApiUrl } from "./internal-session";
import { LOGIN_COOKIE, LOGIN_COOKIE_OPTIONS } from "./login-cookie";
import { safeReturnTo } from "./return-to";

export { LOGIN_COOKIE } from "./login-cookie";
const cookieOptions = {
  httpOnly: true,
  path: "/",
  secure: process.env.NODE_ENV === "production",
};

/** Read server configuration lazily so unconfigured health/build paths still work. */
function settings() {
  const {
    AUTH0_ISSUER,
    AUTH0_CLIENT_ID,
    AUTH0_CLIENT_SECRET,
    AUTH0_AUDIENCE,
    APP_BASE_URL,
    AUTH_SESSION_SECRET,
  } = process.env;
  if (
    !AUTH0_ISSUER ||
    !AUTH0_CLIENT_ID ||
    !AUTH0_CLIENT_SECRET ||
    !AUTH0_AUDIENCE ||
    !APP_BASE_URL ||
    !AUTH_SESSION_SECRET ||
    Buffer.byteLength(AUTH_SESSION_SECRET) < 32
  ) {
    throw new Error("Authentication is not configured");
  }
  const issuer = new URL(AUTH0_ISSUER);
  const base = new URL(APP_BASE_URL);
  if (
    issuer.protocol !== "https:" ||
    issuer.username ||
    issuer.password ||
    issuer.search ||
    issuer.hash ||
    base.username ||
    base.password ||
    base.pathname !== "/" ||
    base.search ||
    base.hash ||
    (base.protocol !== "https:" &&
      (process.env.NODE_ENV === "production" ||
        base.protocol !== "http:" ||
        !["localhost", "127.0.0.1"].includes(base.hostname)))
  ) {
    throw new Error("Invalid authentication origin");
  }
  return {
    issuer,
    base,
    clientId: AUTH0_CLIENT_ID,
    clientSecret: AUTH0_CLIENT_SECRET,
    audience: AUTH0_AUDIENCE,
    key: createHash("sha256").update(AUTH_SESSION_SECRET).digest(),
  };
}

/** Discover only the configured HTTPS issuer and verify signed ID tokens as well. */
async function configuration(config: ReturnType<typeof settings>) {
  return oidc.discovery(
    config.issuer,
    config.clientId,
    config.clientSecret,
    undefined,
    { timeout: 5, execute: [oidc.enableNonRepudiationChecks] },
  );
}

/** Redirect without caching authorization codes or provider credentials. */
function redirect(location: URL | string): Response {
  return new Response(null, {
    status: 303,
    headers: {
      Location: location.toString(),
      "Cache-Control": "no-store",
      "Referrer-Policy": "no-referrer",
    },
  });
}

/** Start a fresh login; a Lax transaction cookie allows the provider's GET callback. */
export async function startLogin(request: Request): Promise<Response> {
  try {
    const config = settings();
    const client = await configuration(config);
    const state = oidc.randomState();
    const nonce = oidc.randomNonce();
    const verifier = oidc.randomPKCECodeVerifier();
    const returnTo = safeReturnTo(
      new URL(request.url).searchParams.get("returnTo"),
    );
    const transaction = await new EncryptJWT({
      state,
      nonce,
      verifier,
      returnTo,
    })
      .setProtectedHeader({ alg: "dir", enc: "A256GCM" })
      .setAudience("iopsych-login")
      .setIssuedAt()
      .setExpirationTime("10m")
      .encrypt(config.key);
    const target = oidc.buildAuthorizationUrl(client, {
      redirect_uri: new URL("/api/auth/callback", config.base).href,
      scope: "openid profile email",
      audience: config.audience,
      state,
      nonce,
      code_challenge: await oidc.calculatePKCECodeChallenge(verifier),
      code_challenge_method: "S256",
      prompt: "login",
    });
    const store = await cookies();
    store.set(LOGIN_COOKIE, transaction, {
      ...LOGIN_COOKIE_OPTIONS,
      maxAge: 600,
    });
    return redirect(target);
  } catch {
    return redirect("/sign-in?error=configuration");
  }
}

/** Consume the transaction, validate OIDC, then let the API authorize the account. */
export async function completeLogin(request: Request): Promise<Response> {
  const store = await cookies();
  const transaction = store.get(LOGIN_COOKIE)?.value;
  store.set(LOGIN_COOKIE, "", {
    ...LOGIN_COOKIE_OPTIONS,
    expires: new Date(0),
    maxAge: 0,
  });
  try {
    const config = settings();
    if (!transaction) throw new Error("Missing transaction");
    const { payload } = await jwtDecrypt(transaction, config.key, {
      audience: "iopsych-login",
      keyManagementAlgorithms: ["dir"],
      contentEncryptionAlgorithms: ["A256GCM"],
    });
    const { state, nonce, verifier } = payload;
    if (
      typeof state !== "string" ||
      typeof nonce !== "string" ||
      typeof verifier !== "string"
    ) {
      throw new Error("Invalid transaction");
    }
    // Use the fixed callback origin, never forwarded/Host headers, for redemption.
    const callback = new URL("/api/auth/callback", config.base);
    callback.search = new URL(request.url).search;
    const tokens = await oidc.authorizationCodeGrant(
      await configuration(config),
      callback,
      {
        expectedState: state,
        expectedNonce: nonce,
        pkceCodeVerifier: verifier,
        idTokenExpected: true,
      },
    );
    if (
      tokens.token_type.toLowerCase() !== "bearer" ||
      tokens.access_token.length > 3800 ||
      !tokens.expires_in ||
      tokens.expires_in <= 0
    )
      throw new Error("Invalid access token");
    const response = await fetch(internalApiUrl("/v1/auth/me"), {
      cache: "no-store",
      signal: AbortSignal.timeout(5000),
      headers: { Authorization: `Bearer ${tokens.access_token}` },
    });
    if (!response.ok) throw new Error("Account unavailable");
    store.set(INTERNAL_SESSION_COOKIE, tokens.access_token, {
      ...cookieOptions,
      sameSite: "strict",
      maxAge: Math.min(tokens.expires_in, 8 * 60 * 60),
    });
    return redirect(new URL(safeReturnTo(payload.returnTo), config.base));
  } catch {
    // Provider errors, codes, tokens and user existence never appear in URLs/logs.
    return redirect("/sign-in?error=login");
  }
}
