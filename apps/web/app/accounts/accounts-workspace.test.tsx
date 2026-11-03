/** @vitest-environment jsdom */
import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
const api = vi.hoisted(() => ({
  getCurrentUser: vi.fn(),
  getManagedUsers: vi.fn(),
  provisionUser: vi.fn(),
  updateManagedUser: vi.fn(),
}));
vi.mock("../../lib/api-client", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../lib/api-client")>()),
  ...api,
}));
import { AccountsWorkspace } from "./accounts-workspace";
import { ApiClientError } from "../../lib/api-client";
const admin = {
  id: "admin",
  organization_id: "org",
  name: "Admin",
  email: "admin@example.invalid",
  role: "admin",
};
const recruiter = {
  id: "recruiter",
  organization_id: "org",
  name: "Recruiter",
  email: "r@example.invalid",
  role: "recruiter",
  auth_subject: "auth0|recruiter",
  is_active: true,
};
beforeEach(() => {
  vi.resetAllMocks();
  api.getCurrentUser.mockResolvedValue(admin);
  api.getManagedUsers.mockResolvedValue([
    { ...admin, auth_subject: "auth0|admin", is_active: true },
    recruiter,
  ]);
});
afterEach(cleanup);
it("provisions an account and changes permissions with explicit active state", async () => {
  const user = userEvent.setup();
  api.provisionUser.mockResolvedValue(recruiter);
  api.updateManagedUser.mockResolvedValue({
    ...recruiter,
    role: "hiring_manager",
    is_active: false,
  });
  render(<AccountsWorkspace />);
  await screen.findByRole("button", { name: "Save access for Recruiter" });
  expect(
    screen.getByRole("button", { name: "Save access for Admin" }),
  ).toBeDisabled();
  await user.type(screen.getByLabelText("Auth0 User ID"), "auth0|new");
  await user.type(screen.getByLabelText("Name"), "New");
  await user.type(screen.getByLabelText("Email"), "new@example.invalid");
  await user.click(screen.getByRole("button", { name: "Provision account" }));
  await waitFor(() =>
    expect(api.provisionUser).toHaveBeenCalledWith({
      auth_subject: "auth0|new",
      name: "New",
      email: "new@example.invalid",
      role: "recruiter",
    }),
  );
  await user.selectOptions(
    screen.getByLabelText("Permission for Recruiter"),
    "hiring_manager",
  );
  await user.click(screen.getByLabelText("Active access for Recruiter"));
  await user.click(
    screen.getByRole("button", { name: "Save access for Recruiter" }),
  );
  await waitFor(() =>
    expect(api.updateManagedUser).toHaveBeenCalledWith(
      "recruiter",
      "hiring_manager",
      false,
    ),
  );
  expect(
    await screen.findByText("auth0|recruiter · Disabled"),
  ).toBeInTheDocument();
});
it("provides sign-in recovery for an expired session", async () => {
  api.getManagedUsers.mockRejectedValue(
    new ApiClientError("Session expired", {
      status: 401,
      code: "authentication_required",
    }),
  );
  render(<AccountsWorkspace />);
  expect(await screen.findByRole("alert")).toHaveTextContent("Session expired");
  expect(screen.getByRole("link", { name: "Sign in again" })).toHaveAttribute(
    "href",
    "/sign-in?returnTo=%2Faccounts",
  );
  expect(
    screen.queryByRole("button", { name: "Provision account" }),
  ).not.toBeInTheDocument();
});
it("announces denied account updates", async () => {
  api.updateManagedUser.mockRejectedValue(new Error("Access denied"));
  render(<AccountsWorkspace />);
  await userEvent.click(
    await screen.findByRole("button", { name: "Save access for Recruiter" }),
  );
  expect(await screen.findByRole("alert")).toHaveTextContent("Access denied");
});
it("does not offer account controls to a nonadministrator", async () => {
  api.getCurrentUser.mockResolvedValue({ ...admin, role: "recruiter" });
  render(<AccountsWorkspace />);
  expect(
    await screen.findByText(
      "Administrator access is required to manage accounts.",
    ),
  ).toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: "Provision account" }),
  ).not.toBeInTheDocument();
});
it("pages accounts using bounded offsets", async () => {
  api.getManagedUsers.mockResolvedValue(
    Array.from({ length: 50 }, (_, index) => ({
      ...recruiter,
      id: `user-${index}`,
      name: `User ${index}`,
    })),
  );
  render(<AccountsWorkspace />);
  const next = await screen.findByRole("button", { name: "Next accounts" });
  await userEvent.click(next);
  await waitFor(() => expect(api.getManagedUsers).toHaveBeenCalledWith(50));
  await userEvent.click(
    screen.getByRole("button", { name: "Previous accounts" }),
  );
  await waitFor(() => expect(api.getManagedUsers).toHaveBeenLastCalledWith(0));
});
