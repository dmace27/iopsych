/** @vitest-environment jsdom */

import "@testing-library/jest-dom/vitest";
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const navigation = vi.hoisted(() => ({
  pathname: "/roles",
  replace: vi.fn(),
  refresh: vi.fn(),
}));
vi.mock("../../lib/api-client", async (original) => ({
  ...(await original<typeof import("../../lib/api-client")>()),
  getCurrentUser: vi.fn(),
}));
import { ApiClientError, getCurrentUser } from "../../lib/api-client";
const account = {
  id: "12345678-1234-4234-8234-123456789abc",
  organization_id: "12345678-1234-4234-8234-123456789abd",
  name: "Synthetic Manager",
  email: "synthetic@example.test",
  role: "hiring_manager" as const,
};
vi.mock("next/navigation", () => ({
  usePathname: () => navigation.pathname,
  useRouter: () => navigation,
}));

import { SiteHeader } from "./site-header";

describe("SiteHeader", () => {
  beforeEach(() => {
    navigation.pathname = "/roles";
    vi.clearAllMocks();
    vi.mocked(getCurrentUser).mockResolvedValue(account);
    vi.stubGlobal("fetch", vi.fn());
  });
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("shows the internal workspace navigation on internal pages", async () => {
    render(<SiteHeader />);
    await screen.findByText(/Synthetic Manager/);
    expect(
      screen.getByRole("navigation", { name: "Primary navigation" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /iopsychrole studio/i }),
    ).toHaveAttribute("href", "/roles");
    expect(screen.getByRole("link", { name: "Privacy" })).toHaveAttribute(
      "href",
      "/privacy",
    );
  });

  it("shows Accounts only for administrators, including on the accounts page", async () => {
    navigation.pathname = "/accounts";
    vi.mocked(getCurrentUser).mockResolvedValue({ ...account, role: "admin" });
    render(<SiteHeader />);
    expect(
      await screen.findByRole("link", { name: "Accounts" }),
    ).toHaveAttribute("href", "/accounts");
    expect(screen.getByRole("link", { name: "Accounts" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    cleanup();
    vi.mocked(getCurrentUser).mockResolvedValue(account);
    render(<SiteHeader />);
    await screen.findByText(/Synthetic Manager/);
    expect(
      screen.queryByRole("link", { name: "Accounts" }),
    ).not.toBeInTheDocument();
  });

  it.each([
    ["/roles", "Roles", "page"],
    ["/roles/12345678-1234-4234-8234-123456789abc", "Roles", "location"],
    ["/reports/12345678-1234-4234-8234-123456789abc", "Roles", "location"],
    ["/privacy", "Privacy", "page"],
    ["/sign-in", "Sign in", "page"],
  ])(
    "identifies the navigation location on %s",
    async (path, name, current) => {
      navigation.pathname = path;
      render(<SiteHeader />);
      if (path !== "/sign-in") await screen.findByText(/Synthetic Manager/);
      expect(screen.getByRole("link", { name })).toHaveAttribute(
        "aria-current",
        current,
      );
      expect(document.querySelectorAll("[aria-current]")).toHaveLength(1);
    },
  );

  it("removes internal navigation from bearer-token candidate pages", () => {
    navigation.pathname = "/candidate/invites/signed-token";
    render(<SiteHeader />);
    expect(screen.queryByRole("navigation")).not.toBeInTheDocument();
    expect(screen.getByText("Candidate assessment")).toBeInTheDocument();
    expect(screen.getByText("Secure invitation")).toBeInTheDocument();
    expect(getCurrentUser).not.toHaveBeenCalled();
    expect(
      screen.queryByRole("button", { name: "Sign out" }),
    ).not.toBeInTheDocument();
  });
});

describe("account session controls", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    navigation.pathname = "/roles/12345678-1234-4234-8234-123456789abc/reports";
    vi.mocked(getCurrentUser).mockResolvedValue(account);
    vi.stubGlobal("fetch", vi.fn());
  });
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("shows name, role and current organization, then signs out with a safe return path", async () => {
    vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 204 }));
    render(<SiteHeader />);
    expect(
      await screen.findByText(/Synthetic Manager · hiring manager/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(`Organization: ${account.organization_id}`),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Sign out" }));
    await waitFor(() =>
      expect(navigation.replace).toHaveBeenCalledWith(
        `/sign-in?returnTo=${encodeURIComponent(navigation.pathname)}`,
      ),
    );
    expect(fetch).toHaveBeenCalledWith("/api/session", {
      method: "DELETE",
      referrerPolicy: "no-referrer",
    });
    expect(navigation.refresh).toHaveBeenCalledOnce();
    expect(screen.queryByText(/Synthetic Manager/)).not.toBeInTheDocument();
  });

  it.each(["http", "network"])(
    "retains the account and permits retry after %s sign-out failure",
    async (failure) => {
      if (failure === "http")
        vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 500 }));
      else vi.mocked(fetch).mockRejectedValue(new Error("offline"));
      render(<SiteHeader />);
      fireEvent.click(await screen.findByRole("button", { name: "Sign out" }));
      expect(await screen.findByRole("alert")).toHaveTextContent(
        "Your session may still be active",
      );
      expect(screen.getByText(/Synthetic Manager/)).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Sign out" })).toBeEnabled();
      expect(navigation.replace).not.toHaveBeenCalled();
      vi.mocked(getCurrentUser).mockRejectedValue(
        new ApiClientError("expired", { status: 401, code: "unauthorized" }),
      );
      fireEvent(window, new Event("focus"));
      await screen.findByRole("link", { name: "Sign in to continue" });
      expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    },
  );

  it("detects expiry on refocus and preserves only the internal pathname", async () => {
    render(<SiteHeader />);
    await screen.findByText(/Synthetic Manager/);
    vi.mocked(getCurrentUser).mockRejectedValue(
      new ApiClientError("expired", { status: 401, code: "unauthorized" }),
    );
    fireEvent(window, new Event("focus"));
    expect(
      await screen.findByRole("link", { name: "Sign in to continue" }),
    ).toHaveAttribute(
      "href",
      `/sign-in?returnTo=${encodeURIComponent(navigation.pathname)}`,
    );
    expect(screen.queryByText(/Synthetic Manager/)).not.toBeInTheDocument();
  });

  it("shows a recovery link for an initially absent session", async () => {
    vi.mocked(getCurrentUser).mockRejectedValue(
      new ApiClientError("missing", { status: 401, code: "unauthorized" }),
    );
    render(<SiteHeader />);
    expect(
      await screen.findByRole("link", { name: "Sign in to continue" }),
    ).toHaveAttribute("referrerpolicy", "no-referrer");
  });

  it("does not mislabel a service failure as expiry", async () => {
    vi.mocked(getCurrentUser).mockRejectedValue(new Error("offline"));
    render(<SiteHeader />);
    expect(
      await screen.findByText(/Account details unavailable/),
    ).toBeInTheDocument();
    expect(screen.queryByText(/session has expired/)).not.toBeInTheDocument();
  });

  it.each([
    "/candidate",
    "/candidate/invites/synthetic-secret",
    "/sign-in",
    "/unknown",
  ])("does not fetch internal account on %s", (path) => {
    navigation.pathname = path;
    render(<SiteHeader />);
    expect(getCurrentUser).not.toHaveBeenCalled();
  });

  it("hides account state immediately when navigating to a candidate page", async () => {
    const view = render(<SiteHeader />);
    await screen.findByText(/Synthetic Manager/);
    navigation.pathname = "/candidate/invites/synthetic-secret";
    view.rerender(<SiteHeader />);
    fireEvent(window, new Event("focus"));
    expect(screen.queryByText(/Synthetic Manager/)).not.toBeInTheDocument();
    expect(getCurrentUser).toHaveBeenCalledOnce();
  });

  it("ignores an outstanding account request after unmount", async () => {
    let resolve!: (user: typeof account) => void;
    vi.mocked(getCurrentUser).mockReturnValue(
      new Promise((done) => {
        resolve = done;
      }),
    );
    const view = render(<SiteHeader />);
    view.unmount();
    await act(async () => resolve(account));
    expect(screen.queryByText(/Synthetic Manager/)).not.toBeInTheDocument();
  });
});
