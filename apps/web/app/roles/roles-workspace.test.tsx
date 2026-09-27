/** @vitest-environment jsdom */

import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const apiMocks = vi.hoisted(() => ({
  createRole: vi.fn(),
  getCurrentUser: vi.fn(),
  getRoles: vi.fn(),
}));
const navigationMocks = vi.hoisted(() => ({ push: vi.fn() }));

vi.mock("next/navigation", () => ({
  useRouter: () => navigationMocks,
}));
vi.mock("../../lib/api-client", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../lib/api-client")>()),
  ...apiMocks,
}));

import type { CurrentUser, Role } from "../../lib/contracts";
import { RolesWorkspace } from "./roles-workspace";

const ROLE_ID = "11111111-1111-4111-8111-111111111111";
const ORGANIZATION_ID = "22222222-2222-4222-8222-222222222222";

/** Build a valid current-user contract for a requested authorization role. */
function currentUser(role: CurrentUser["role"]): CurrentUser {
  return {
    email: `${role}@example.invalid`,
    id: "33333333-3333-4333-8333-333333333333",
    name: "Internal Reviewer",
    organization_id: ORGANIZATION_ID,
    role,
  };
}

/** Build the role returned after a successful draft creation. */
function role(): Role {
  return {
    created_at: "2026-09-26T12:00:00Z",
    department: "Engineering",
    id: ROLE_ID,
    job_description: "Own service reliability and incident response.",
    location: "Toronto",
    organization_id: ORGANIZATION_ID,
    status: "draft",
    title: "Platform Engineer",
  };
}

describe("RolesWorkspace", () => {
  beforeEach(() => {
    apiMocks.createRole.mockReset();
    apiMocks.getCurrentUser.mockReset();
    apiMocks.getRoles.mockReset();
    navigationMocks.push.mockReset();
  });

  afterEach(cleanup);

  it("supports keyboard-accessible recruiter role creation", async () => {
    apiMocks.getRoles.mockResolvedValue([]);
    apiMocks.getCurrentUser.mockResolvedValue(currentUser("recruiter"));
    apiMocks.createRole.mockResolvedValue(role());
    const user = userEvent.setup();
    render(<RolesWorkspace />);

    const createButton = await screen.findByRole("button", {
      name: "Create role",
    });
    createButton.focus();
    await user.keyboard("{Enter}");

    const title = screen.getByRole("textbox", { name: "Role title" });
    expect(title).toHaveFocus();
    await user.type(title, "Platform Engineer");
    await user.type(
      screen.getByRole("textbox", { name: "Department" }),
      "Engineering",
    );
    await user.type(
      screen.getByRole("textbox", { name: "Location" }),
      "Toronto",
    );
    await user.type(
      screen.getByRole("textbox", { name: /job description/i }),
      "Own service reliability and incident response.",
    );
    await user.click(screen.getByRole("button", { name: "Create draft role" }));

    await waitFor(() => {
      expect(apiMocks.createRole).toHaveBeenCalledWith({
        department: "Engineering",
        job_description: "Own service reliability and incident response.",
        location: "Toronto",
        title: "Platform Engineer",
      });
      expect(navigationMocks.push).toHaveBeenCalledWith(`/roles/${ROLE_ID}`);
    });
  });

  it("shows a manager the permission-aware empty state without authoring controls", async () => {
    apiMocks.getRoles.mockResolvedValue([]);
    apiMocks.getCurrentUser.mockResolvedValue(currentUser("hiring_manager"));
    render(<RolesWorkspace />);

    expect(await screen.findByText("No roles yet")).toBeInTheDocument();
    expect(
      screen.getByText(/a recruiter has not created a role/i),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Create role" }),
    ).not.toBeInTheDocument();
  });

  it("announces a loading failure and recovers through the retry action", async () => {
    apiMocks.getRoles
      .mockRejectedValueOnce(new Error("Temporary service failure"))
      .mockResolvedValueOnce([role()]);
    apiMocks.getCurrentUser.mockResolvedValue(currentUser("recruiter"));
    const user = userEvent.setup();
    render(<RolesWorkspace />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Temporary service failure",
    );
    await user.click(screen.getByRole("button", { name: "Try again" }));

    expect(
      await screen.findByRole("link", { name: /platform engineer/i }),
    ).toHaveAttribute("href", `/roles/${ROLE_ID}`);
  });
});
