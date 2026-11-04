/** @vitest-environment jsdom */
import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
vi.mock("./sign-in-form", () => ({
  SignInForm: ({
    localLogin,
    tokenLogin,
    returnTo,
  }: {
    localLogin: boolean;
    tokenLogin: boolean;
    returnTo: string;
  }) => (
    <div
      data-testid="form"
      data-local={String(localLogin)}
      data-token={String(tokenLogin)}
      data-return-to={returnTo}
    />
  ),
}));
import SignInPage from "./page";

afterEach(() => {
  cleanup();
  vi.unstubAllEnvs();
});

describe("sign-in page", () => {
  it("does not offer token paste in production even when fixture exchange is enabled", async () => {
    vi.stubEnv("NODE_ENV", "production");
    vi.stubEnv("ENABLE_TOKEN_SIGN_IN", "true");
    render(await SignInPage({ searchParams: Promise.resolve({}) }));
    expect(screen.getByTestId("form")).toHaveAttribute("data-token", "false");
  });
  it.each([
    ["development", "true", "true"],
    ["development", "false", "false"],
    ["production", "true", "false"],
    ["test", "true", "false"],
  ])(
    "retains the local login guard for %s / %s",
    async (mode, enabled, expected) => {
      vi.stubEnv("NODE_ENV", mode);
      vi.stubEnv("LOCAL_LOGIN_ENABLED", enabled);
      render(
        await SignInPage({
          searchParams: Promise.resolve({ returnTo: "/privacy" }),
        }),
      );
      expect(screen.getByTestId("form")).toHaveAttribute(
        "data-local",
        expected,
      );
      expect(screen.getByTestId("form")).toHaveAttribute(
        "data-return-to",
        "/privacy",
      );
    },
  );

  it.each([
    "//example.test",
    "/candidate/invites/synthetic-secret",
    ["/privacy", "/roles"],
    undefined,
  ])("sanitizes returnTo before passing it to the client", async (returnTo) => {
    render(await SignInPage({ searchParams: Promise.resolve({ returnTo }) }));
    expect(screen.getByTestId("form")).toHaveAttribute(
      "data-return-to",
      "/roles",
    );
  });
});
