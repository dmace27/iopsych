/** @vitest-environment jsdom */
import "@testing-library/jest-dom/vitest";
import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
const navigation = vi.hoisted(() => ({ replace: vi.fn(), refresh: vi.fn() }));
const api = vi.hoisted(() => ({ getCurrentUser: vi.fn() }));
vi.mock("../../lib/api-client", () => api);
vi.mock("next/navigation", () => ({
  usePathname: () => "/reports/report-id",
  useRouter: () => navigation,
}));
import { AccountMenu } from "./account-menu";
beforeEach(() => {
  api.getCurrentUser.mockReset();
  vi.stubGlobal("fetch", vi.fn());
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
it("shows account, organization, permission and administrator navigation", async () => {
  api.getCurrentUser.mockResolvedValue({
    name: "Pilot Admin",
    organization_name: "Pilot Organization",
    organization_id: "pilot-org",
    role: "admin",
  });
  render(<AccountMenu />);
  expect(await screen.findByText("Pilot Admin · admin")).toBeInTheDocument();
  expect(
    screen.getByText("Organization: Pilot Organization"),
  ).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Accounts" })).toHaveAttribute(
    "href",
    "/accounts",
  );
  expect(screen.getByRole("button", { name: "Sign out" })).toBeInTheDocument();
});
it.each([new Response(null, { status: 500 }), new Error("offline")])(
  "retains a retry action after sign-out fails",
  async (failure) => {
    api.getCurrentUser.mockResolvedValue({
      name: "Recruiter",
      organization_id: "pilot-org",
      role: "recruiter",
    });
    if (failure instanceof Error) vi.mocked(fetch).mockRejectedValue(failure);
    else vi.mocked(fetch).mockResolvedValue(failure);
    render(<AccountMenu />);
    await userEvent.click(
      await screen.findByRole("button", { name: "Sign out" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent("Try again");
    expect(fetch).toHaveBeenCalledWith("/api/session", { method: "DELETE" });
    expect(
      screen.queryByRole("link", { name: "Accounts" }),
    ).not.toBeInTheDocument();
  },
);
it("offers return-path recovery when account authorization expires", async () => {
  api.getCurrentUser.mockRejectedValue(new Error("expired"));
  render(<AccountMenu />);
  await waitFor(() => expect(api.getCurrentUser).toHaveBeenCalled());
  expect(screen.getByRole("link", { name: "Sign in" })).toHaveAttribute(
    "href",
    "/sign-in?returnTo=%2Freports%2Freport-id",
  );
});

it("clears the browser session and returns to sign-in", async () => {
  api.getCurrentUser.mockResolvedValue({
    name: "Recruiter",
    organization_id: "pilot-org",
    role: "recruiter",
  });
  vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 204 }));
  render(<AccountMenu />);
  await userEvent.click(
    await screen.findByRole("button", { name: "Sign out" }),
  );
  await waitFor(() =>
    expect(navigation.replace).toHaveBeenCalledWith("/sign-in"),
  );
  expect(navigation.refresh).toHaveBeenCalled();
  expect(
    screen.queryByRole("button", { name: "Sign out" }),
  ).not.toBeInTheDocument();
});

it("offers sign-in immediately when a workspace request loses its session", async () => {
  api.getCurrentUser.mockResolvedValue({
    name: "Recruiter",
    organization_id: "pilot-org",
    role: "recruiter",
  });
  render(<AccountMenu />);
  await screen.findByRole("button", { name: "Sign out" });
  act(() => window.dispatchEvent(new Event("iopsych:session-expired")));
  expect(screen.getByRole("link", { name: "Sign in" })).toHaveAttribute(
    "href",
    "/sign-in?returnTo=%2Freports%2Freport-id",
  );
});
