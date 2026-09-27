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

  it("establishes a server session and navigates to the roles workspace", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify({ role: "recruiter" }), { status: 200 }),
    );
    const user = userEvent.setup();
    render(<SignInForm />);

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

  it("announces a rejected credential and restores the interactive form", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify({ detail: "The token is invalid." }), {
        status: 401,
      }),
    );
    const user = userEvent.setup();
    render(<SignInForm />);

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
});
