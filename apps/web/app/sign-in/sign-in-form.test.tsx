/** @vitest-environment jsdom */

import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const navigationMocks = vi.hoisted(() => ({
  refresh: vi.fn(),
  replace: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => navigationMocks,
}));

import { SignInForm } from "./sign-in-form";

describe("SignInForm", () => {
  beforeEach(() => {
    navigationMocks.refresh.mockReset();
    navigationMocks.replace.mockReset();
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("defaults to provider navigation without a token field or browser token exchange", () => {
    render(<SignInForm returnTo="/accounts" />);
    expect(
      screen.queryByLabelText(/internal access token/i),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Sign in with Auth0" }),
    ).toHaveAttribute("href", "/api/auth/login?returnTo=%2Faccounts");
    expect(fetch).not.toHaveBeenCalled();
  });

  it.each(["configuration", "provider-secret-error"])(
    "shows safe provider feedback for %s",
    (providerError) => {
      render(
        <SignInForm providerError={providerError} returnTo="//evil.test" />,
      );
      expect(screen.getByRole("alert")).toHaveTextContent(
        providerError === "configuration"
          ? "Sign-in is not configured."
          : "Sign-in could not be completed.",
      );
      expect(screen.getByRole("alert")).not.toHaveTextContent(
        "provider-secret-error",
      );
      expect(
        screen.getByRole("link", { name: "Sign in with Auth0" }),
      ).toHaveAttribute("href", "/api/auth/login?returnTo=%2Froles");
    },
  );

  it("establishes a server session and navigates to the roles workspace", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify({ role: "recruiter" }), { status: 200 }),
    );
    const user = userEvent.setup();
    render(<SignInForm tokenLogin />);

    const tokenInput = screen.getByLabelText(/internal access token/i);
    await user.type(tokenInput, "provider-token");
    await user.click(screen.getByRole("button", { name: "Continue to roles" }));

    expect(fetch).toHaveBeenCalledWith(
      "/api/session",
      expect.objectContaining({
        body: JSON.stringify({ token: "provider-token" }),
        method: "POST",
      }),
    );
    await waitFor(() => {
      expect(navigationMocks.replace).toHaveBeenCalledWith("/roles");
      expect(navigationMocks.refresh).toHaveBeenCalledOnce();
    });
  });

  it("signs in with a selected synthetic account without a token input", async () => {
    vi.mocked(fetch).mockResolvedValue(Response.json({ status: "ok" }));
    const user = userEvent.setup();
    render(<SignInForm localLogin />);
    expect(
      screen.queryByLabelText(/internal access token/i),
    ).not.toBeInTheDocument();
    await user.selectOptions(
      screen.getByLabelText(/synthetic local account/i),
      "beacon",
    );
    await user.click(screen.getByRole("button", { name: "Continue to roles" }));
    expect(fetch).toHaveBeenCalledWith(
      "/api/session/local",
      expect.objectContaining({
        body: JSON.stringify({ identity: "beacon" }),
        method: "POST",
      }),
    );
    await waitFor(() =>
      expect(navigationMocks.replace).toHaveBeenCalledWith("/roles"),
    );
  });

  it("announces a rejected credential and restores the interactive form", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify({ detail: "The token is invalid." }), {
        status: 401,
      }),
    );
    const user = userEvent.setup();
    render(<SignInForm tokenLogin />);

    await user.type(screen.getByLabelText(/internal access token/i), "bad");
    await user.click(screen.getByRole("button", { name: "Continue to roles" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The token is invalid.",
    );
    expect(
      screen.getByRole("button", { name: "Continue to roles" }),
    ).toBeEnabled();
    expect(navigationMocks.replace).not.toHaveBeenCalled();
  });
  it.each([
    ["/privacy", "/privacy"],
    [
      "/reports/12345678-1234-4234-8234-123456789abc",
      "/reports/12345678-1234-4234-8234-123456789abc",
    ],
    ["//evil.test", "/roles"],
    ["/candidate/invites/secret", "/roles"],
    ["/privacy?token=secret", "/roles"],
  ])(
    "validates returnTo %s before post-login navigation",
    async (returnTo, expected) => {
      vi.mocked(fetch).mockResolvedValue(Response.json({ status: "ok" }));
      const user = userEvent.setup();
      render(<SignInForm localLogin returnTo={returnTo} />);
      await user.click(
        screen.getByRole("button", { name: "Continue to roles" }),
      );
      await waitFor(() =>
        expect(navigationMocks.replace).toHaveBeenCalledWith(expected),
      );
      expect(fetch).toHaveBeenCalledWith(
        "/api/session/local",
        expect.objectContaining({
          body: JSON.stringify({ identity: "alpha" }),
        }),
      );
    },
  );
});
