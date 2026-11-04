/** Shared transaction-cookie policy, without loading the provider SDK on logout. */
export const LOGIN_COOKIE =
  process.env.NODE_ENV === "production"
    ? "__Host-iopsych_login"
    : "iopsych_login";

export const LOGIN_COOKIE_OPTIONS = {
  httpOnly: true,
  path: "/",
  secure: process.env.NODE_ENV === "production",
  sameSite: "lax",
} as const;
