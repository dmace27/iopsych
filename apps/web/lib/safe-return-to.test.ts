import { describe, expect, it } from "vitest";
import {
  isInternalAccountPath,
  safeReturnTo,
  signInHref,
} from "./safe-return-to";

const id = "12345678-1234-4234-8234-123456789abc";
describe("safeReturnTo", () => {
  it.each([
    "/roles",
    `/roles/${id}`,
    `/roles/${id}/reports`,
    `/roles/${id}/invites`,
    `/reports/${id}`,
    "/privacy",
    "/accounts",
  ])("preserves %s", (path) => {
    expect(safeReturnTo(path)).toBe(path);
    expect(isInternalAccountPath(path)).toBe(true);
    expect(signInHref(path)).toBe(
      `/sign-in?returnTo=${encodeURIComponent(path)}`,
    );
  });
  it.each([
    "/accounts/",
    "/accounts?token=secret",
    "/accounts#secret",
    "/accounts/users",
    undefined,
    null,
    ["/privacy"],
    "https://example.test",
    "//example.test",
    "/\\example.test",
    "\\\\example.test",
    "javascript:alert(1)",
    "/%2f%2fexample.test",
    "%2Fprivacy",
    "/roles%252f..",
    "/roles/../privacy",
    "/roles\n",
    "/privacy\n",
    "/privacy\r",
    "/privacy?token=secret",
    "/privacy#secret",
    "/candidate/invites/secret",
    "/reports",
    "/roles/not-a-uuid",
    `/roles/${id}/profiles`,
    `/roles/${id}/invites?token=secret`,
    `/roles/${id}/invites/secret`,
    `/reports/${id}/extra`,
    "/privacy/",
    "/api/session",
    " /privacy",
    "/roles/00000000-0000-0000-0000-000000000000",
  ])("rejects %s", (path) => {
    expect(safeReturnTo(path)).toBe("/roles");
  });
});
