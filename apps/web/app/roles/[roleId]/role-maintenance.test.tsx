/** @vitest-environment jsdom */
import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { RoleMaintenance } from "./role-maintenance";
import type { Role } from "../../../lib/contracts";
const mocks = vi.hoisted(() => ({ updateRole: vi.fn(), archiveRole: vi.fn() }));
vi.mock("../../../lib/role-maintenance-client", () => mocks);
const role: Role = {
  id: "55555555-5555-4555-8555-555555555555",
  organization_id: "22222222-2222-4222-8222-222222222222",
  title: "Engineer",
  department: "Engineering",
  location: "Toronto",
  job_description: "Maintain services.",
  status: "active",
  created_at: "2026-09-26T12:00:00Z",
};
beforeEach(() => {
  vi.resetAllMocks();
  HTMLDialogElement.prototype.showModal = function () {
    this.setAttribute("open", "");
  };
  HTMLDialogElement.prototype.close = function () {
    this.removeAttribute("open");
  };
});
afterEach(cleanup);
it.each(["admin", "recruiter"] as const)(
  "saves only changed trimmed metadata for %s",
  async (userRole) => {
    const user = userEvent.setup();
    const changed = vi.fn();
    mocks.updateRole.mockResolvedValue({ ...role, title: "Updated" });
    render(
      <RoleMaintenance role={role} userRole={userRole} onChanged={changed} />,
    );
    await user.click(screen.getByText("Edit role details"));
    const title = screen.getByLabelText(/Role title/);
    await user.clear(title);
    await user.type(title, " Updated ");
    await user.click(screen.getByText("Save role details"));
    expect(mocks.updateRole).toHaveBeenCalledWith(role.id, {
      title: "Updated",
    });
    expect(changed).toHaveBeenCalledWith({ ...role, title: "Updated" });
  },
);
it("rejects whitespace and empty patches without issuing a request", async () => {
  const user = userEvent.setup();
  render(<RoleMaintenance role={role} userRole="admin" onChanged={vi.fn()} />);
  await user.click(screen.getByText("Edit role details"));
  await user.click(screen.getByText("Save role details"));
  expect(screen.getByRole("alert")).toHaveTextContent("Change at least one");
  await user.clear(screen.getByLabelText(/Role title/));
  await user.type(screen.getByLabelText(/Role title/), "   ");
  await user.click(screen.getByText("Save role details"));
  expect(mocks.updateRole).not.toHaveBeenCalled();
});
it("keeps failed edits and allows retry", async () => {
  const user = userEvent.setup();
  mocks.updateRole.mockRejectedValue(
    new Error("Refresh to check whether it was archived."),
  );
  const changed = vi.fn();
  render(<RoleMaintenance role={role} userRole="admin" onChanged={changed} />);
  await user.click(screen.getByText("Edit role details"));
  await user.type(screen.getByLabelText(/Location/), " West");
  await user.click(screen.getByText("Save role details"));
  expect(screen.getByRole("alert")).toHaveTextContent("Refresh");
  expect(screen.getByLabelText(/Location/)).toHaveValue("Toronto West");
  expect(changed).not.toHaveBeenCalled();
});
it("requires confirmation, focuses safe cancel, and waits for server archive", async () => {
  const user = userEvent.setup();
  let resolve!: () => void;
  mocks.archiveRole.mockReturnValue(
    new Promise<void>((done) => {
      resolve = done;
    }),
  );
  const changed = vi.fn();
  render(
    <RoleMaintenance role={role} userRole="recruiter" onChanged={changed} />,
  );
  await user.click(screen.getByText("Archive role"));
  expect(screen.getByText("Keep role")).toHaveFocus();
  await user.click(screen.getByText("Keep role"));
  expect(mocks.archiveRole).not.toHaveBeenCalled();
  expect(screen.getByText("Archive role")).toHaveFocus();
  await user.click(screen.getByText("Archive role"));
  await user.click(screen.getByText("Confirm archive"));
  expect(screen.getByText("Archiving role…")).toBeDisabled();
  expect(changed).not.toHaveBeenCalled();
  resolve();
  await waitFor(() =>
    expect(changed).toHaveBeenCalledWith({ ...role, status: "archived" }),
  );
  expect(
    screen.getByRole("heading", { name: "Role maintenance" }),
  ).toHaveFocus();
});
it("shows archive errors in the dialog and permits retry", async () => {
  mocks.archiveRole.mockRejectedValue(new Error("Archive failed"));
  const user = userEvent.setup();
  render(<RoleMaintenance role={role} userRole="admin" onChanged={vi.fn()} />);
  await user.click(screen.getByText("Archive role"));
  await user.click(screen.getByText("Confirm archive"));
  expect(screen.getByRole("alert")).toHaveTextContent("Archive failed");
  expect(screen.getByText("Confirm archive")).toBeEnabled();
});
it("keeps managers and archived roles read-only", () => {
  const { rerender } = render(
    <RoleMaintenance
      role={role}
      userRole="hiring_manager"
      onChanged={vi.fn()}
    />,
  );
  expect(screen.queryByRole("button")).not.toBeInTheDocument();
  rerender(
    <RoleMaintenance
      role={{ ...role, status: "archived" }}
      userRole="admin"
      onChanged={vi.fn()}
    />,
  );
  expect(screen.queryByRole("button")).not.toBeInTheDocument();
  expect(screen.getByText("This archived role is read-only.")).toBeVisible();
});
