/** @vitest-environment jsdom */

import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const navigation = vi.hoisted(() => ({ pathname: "/roles" }));
vi.mock("next/navigation", () => ({ usePathname: () => navigation.pathname }));

import { SiteHeader } from "./site-header";

describe("SiteHeader", () => {
  beforeEach(() => {
    navigation.pathname = "/roles";
  });
  afterEach(cleanup);

  it("shows the internal workspace navigation on internal pages", () => {
    render(<SiteHeader />);
    expect(
      screen.getByRole("navigation", { name: "Primary navigation" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /iopsychrole studio/i }),
    ).toHaveAttribute("href", "/roles");
  });

  it("removes internal navigation from bearer-token candidate pages", () => {
    navigation.pathname = "/candidate/invites/signed-token";
    render(<SiteHeader />);
    expect(screen.queryByRole("navigation")).not.toBeInTheDocument();
    expect(screen.getByText("Candidate assessment")).toBeInTheDocument();
    expect(screen.getByText("Secure invitation")).toBeInTheDocument();
  });
});
