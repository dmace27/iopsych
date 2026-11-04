// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { InvitationWorkspace } from "./invitation-workspace";
const api = vi.hoisted(() => ({
  user: vi.fn(),
  role: vi.fn(),
  profiles: vi.fn(),
  list: vi.fn(),
  issue: vi.fn(),
}));
vi.mock("../../../../lib/api-client", async (original) => ({
  ...(await original<typeof import("../../../../lib/api-client")>()),
  getCurrentUser: api.user,
  getRole: api.role,
  getRoleProfiles: api.profiles,
}));
vi.mock("../../../../lib/invitation-client", () => ({
  getInvitations: api.list,
  revokeInvitation: vi.fn(),
}));
vi.mock("../../../../lib/invitation-issuance-client", () => ({
  issueInvitation: api.issue,
}));
const id = "00000000-0000-4000-8000-000000000002";
beforeEach(() => {
  vi.resetAllMocks();
  api.user.mockResolvedValue({ role: "recruiter" });
  api.role.mockResolvedValue({ title: "Synthetic role", status: "active" });
  api.profiles.mockResolvedValue([{ id, version: 2, status: "approved" }]);
  api.list.mockResolvedValue({ items: [], next_cursor: null });
  api.issue.mockResolvedValue({ status: "active" });
});
afterEach(cleanup);
async function review() {
  const user = userEvent.setup();
  await user.type(
    await screen.findByLabelText("Recipient email"),
    "synthetic@example.invalid",
  );
  await user.selectOptions(
    screen.getByLabelText("Approved profile version"),
    id,
  );
  await user.click(screen.getByRole("button", { name: "Review invitation" }));
  return user;
}
it("refreshes history after issuance while retaining factual completion", async () => {
  render(<InvitationWorkspace roleId="role" />);
  const user = await review();
  await user.click(
    screen.getByRole("button", { name: "Confirm and issue invitation" }),
  );
  await waitFor(() => expect(api.list).toHaveBeenCalledTimes(2));
  expect(screen.getByText(/Stored status: active/)).toHaveTextContent(
    "Delivery receipt is not confirmed here",
  );
  expect(
    screen.getByRole("button", { name: "Confirm and issue invitation" }),
  ).toBeDisabled();
});
it("preserves the retry key when history is refreshed after an uncertain outcome", async () => {
  api.issue.mockRejectedValueOnce(new Error("uncertain"));
  render(<InvitationWorkspace roleId="role" />);
  const user = await review();
  await user.click(
    screen.getByRole("button", { name: "Confirm and issue invitation" }),
  );
  await screen.findByRole("alert");
  await user.click(
    screen.getByRole("button", { name: "Refresh invitation history" }),
  );
  await waitFor(() => expect(api.list).toHaveBeenCalledTimes(2));
  await user.click(
    screen.getByRole("button", { name: "Confirm and retry invitation" }),
  );
  expect(api.issue.mock.calls[1][2]).toBe(api.issue.mock.calls[0][2]);
});
it("does not load issuance profiles for an archived role", async () => {
  api.role.mockResolvedValue({ title: "Archived role", status: "archived" });
  render(<InvitationWorkspace roleId="role" />);
  expect(
    await screen.findByText("Archived roles cannot issue invitations."),
  ).toBeVisible();
  expect(api.profiles).not.toHaveBeenCalled();
});
it("does not expose issuance to managers", async () => {
  api.user.mockResolvedValue({ role: "hiring_manager" });
  render(<InvitationWorkspace roleId="role" />);
  await screen.findByRole("alert");
  expect(api.profiles).not.toHaveBeenCalled();
  expect(screen.queryByText("Issue invitation")).not.toBeInTheDocument();
});
it("disables history actions during issuance and restores them on failure", async () => {
  let fail!: (reason: unknown) => void;
  api.issue.mockImplementation(
    () =>
      new Promise((_, reject) => {
        fail = reject;
      }),
  );
  render(<InvitationWorkspace roleId="role" />);
  const user = await review();
  await user.click(
    screen.getByRole("button", { name: "Confirm and issue invitation" }),
  );
  expect(
    screen.getByRole("button", { name: "Refresh invitation history" }),
  ).toBeDisabled();
  fail(new Error("uncertain"));
  await screen.findByRole("alert");
  expect(
    screen.getByRole("button", { name: "Refresh invitation history" }),
  ).toBeEnabled();
});
