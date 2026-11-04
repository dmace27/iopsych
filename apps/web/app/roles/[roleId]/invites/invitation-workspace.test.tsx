// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { ApiClientError } from "../../../../lib/api-client";
import { InvitationWorkspace } from "./invitation-workspace";
const api = vi.hoisted(() => ({
  getCurrentUser: vi.fn(),
  getRole: vi.fn(),
  getInvitations: vi.fn(),
  revokeInvitation: vi.fn(),
}));
vi.mock("../../../../lib/api-client", async (original) => ({
  ...(await original<typeof import("../../../../lib/api-client")>()),
  getCurrentUser: api.getCurrentUser,
  getRole: api.getRole,
}));
vi.mock("../../../../lib/invitation-client", () => ({
  getInvitations: api.getInvitations,
  revokeInvitation: api.revokeInvitation,
}));
const invite = {
  id: "invite",
  role_profile_id: "profile",
  email: "synthetic@example.invalid",
  status: "active",
  created_at: "2020-01-01T00:00:00Z",
  expires_at: "2020-01-02T00:00:00Z",
  sent_at: null,
  revoked_at: null,
};
beforeEach(() => {
  vi.resetAllMocks();
  api.getCurrentUser.mockResolvedValue({ role: "recruiter" });
  api.getRole.mockResolvedValue({ title: "Archived role", status: "archived" });
  api.getInvitations.mockResolvedValue({ items: [invite], next_cursor: null });
  api.revokeInvitation.mockResolvedValue({ ...invite, status: "revoked" });
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});
it("shows stored active status despite past expiry and nullable sent time", async () => {
  render(<InvitationWorkspace roleId="role" />);
  expect(await screen.findByText("Active")).toBeVisible();
  expect(screen.getByText(/No sent time recorded/)).toBeVisible();
  expect(
    screen.queryByText("Expired", { exact: true }),
  ).not.toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: "Load more invitations" }),
  ).not.toBeInTheDocument();
});
it.each(["admin", "recruiter"])(
  "allows %s, confirms/cancels revoke and prevents duplicate requests",
  async (role) => {
    api.getCurrentUser.mockResolvedValue({ role });
    const confirm = vi
      .spyOn(window, "confirm")
      .mockReturnValueOnce(false)
      .mockReturnValue(true);
    let finish!: (value: unknown) => void;
    api.revokeInvitation.mockImplementation(
      () =>
        new Promise((resolve) => {
          finish = resolve;
        }),
    );
    const user = userEvent.setup();
    render(<InvitationWorkspace roleId="role" />);
    const revoke = await screen.findByRole("button", {
      name: /Revoke invitation for/,
    });
    await user.click(revoke);
    expect(api.revokeInvitation).not.toHaveBeenCalled();
    await user.dblClick(revoke);
    expect(api.revokeInvitation).toHaveBeenCalledTimes(1);
    expect(confirm).toHaveBeenCalledTimes(2);
    expect(revoke).toBeDisabled();
    finish({ ...invite, status: "revoked" });
    expect(await screen.findByText("Revoked", { exact: true })).toBeVisible();
  },
);
it("does not request invitation data for a hiring manager", async () => {
  api.getCurrentUser.mockResolvedValue({ role: "hiring_manager" });
  render(<InvitationWorkspace roleId="role" />);
  expect(await screen.findByRole("alert")).toHaveTextContent("Only recruiters");
  expect(api.getInvitations).not.toHaveBeenCalled();
});
it("paginates by exact server cursor, keeps rows on failure, and restarts invalid cursors", async () => {
  api.getInvitations
    .mockResolvedValueOnce({ items: [invite], next_cursor: "opaque" })
    .mockRejectedValueOnce(
      new ApiClientError("private", {
        status: 422,
        code: "invalid_invitation_cursor",
      }),
    )
    .mockResolvedValueOnce({ items: [], next_cursor: null });
  const user = userEvent.setup();
  render(<InvitationWorkspace roleId="role" />);
  await user.click(
    await screen.findByRole("button", { name: "Load more invitations" }),
  );
  expect(api.getInvitations).toHaveBeenLastCalledWith("role", "opaque");
  expect(screen.getByText(invite.email)).toBeVisible();
  await user.click(await screen.findByRole("button", { name: "Restart list" }));
  expect(await screen.findByText("No invitations yet")).toBeVisible();
  expect(api.getInvitations).toHaveBeenLastCalledWith("role");
});
it("appends later pages and exhausts only on null cursor", async () => {
  api.getInvitations
    .mockResolvedValueOnce({ items: [invite], next_cursor: "cursor" })
    .mockResolvedValueOnce({
      items: [
        {
          ...invite,
          id: "two",
          email: "second@example.invalid",
          status: "consented",
        },
      ],
      next_cursor: null,
    });
  const user = userEvent.setup();
  render(<InvitationWorkspace roleId="role" />);
  await user.click(
    await screen.findByRole("button", { name: "Load more invitations" }),
  );
  expect(await screen.findByText("second@example.invalid")).toBeVisible();
  expect(screen.getByText(invite.email)).toBeVisible();
  expect(
    screen.queryByRole("button", { name: "Load more invitations" }),
  ).not.toBeInTheDocument();
});
it("offers safe retry and sign-in recovery", async () => {
  api.getCurrentUser.mockRejectedValueOnce(new Error("secret URL"));
  const user = userEvent.setup();
  render(<InvitationWorkspace roleId="role" />);
  expect(await screen.findByRole("alert")).not.toHaveTextContent("secret");
  await user.click(screen.getByRole("button", { name: "Try again" }));
  await screen.findByText(invite.email);
  vi.spyOn(window, "confirm").mockReturnValue(true);
  api.revokeInvitation.mockRejectedValue(
    new ApiClientError("secret", { status: 401, code: "unauthorized" }),
  );
  await user.click(
    screen.getByRole("button", { name: /Revoke invitation for/ }),
  );
  expect(
    await screen.findByRole("link", { name: "Sign in to manage invitations" }),
  ).toHaveAttribute("href", "/sign-in?returnTo=%2Froles%2Frole%2Finvites");
  expect(screen.queryByText(invite.email)).not.toBeInTheDocument();
});
it("ignores stale responses when switching role", async () => {
  let finish!: (value: unknown) => void;
  api.getInvitations
    .mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          finish = resolve;
        }),
    )
    .mockResolvedValue({ items: [], next_cursor: null });
  const view = render(<InvitationWorkspace roleId="old" />);
  await waitFor(() => expect(api.getInvitations).toHaveBeenCalledWith("old"));
  view.rerender(<InvitationWorkspace roleId="new" />);
  await screen.findByText("No invitations yet");
  finish({ items: [invite], next_cursor: null });
  expect(screen.queryByText(invite.email)).not.toBeInTheDocument();
});

it("retries revoke only after a fresh confirmation and keeps stored state on failure", async () => {
  const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
  api.revokeInvitation
    .mockRejectedValueOnce(
      new ApiClientError("private", { status: 429, code: "rate_limit" }),
    )
    .mockResolvedValueOnce({ ...invite, status: "revoked" });
  const user = userEvent.setup();
  render(<InvitationWorkspace roleId="role" />);
  await user.click(
    await screen.findByRole("button", { name: /Revoke invitation for/ }),
  );
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Wait before trying again",
  );
  expect(screen.getByText("Active")).toBeVisible();
  await user.click(screen.getByRole("button", { name: "Try again" }));
  expect(await screen.findByText("Revoked", { exact: true })).toBeVisible();
  expect(confirm).toHaveBeenCalledTimes(2);
});
it.each([403, 404])(
  "honors API denial (%s) after a successful permission lookup",
  async (status) => {
    api.getInvitations.mockRejectedValue(
      new ApiClientError("private", { status, code: "denied" }),
    );
    render(<InvitationWorkspace roleId="foreign" />);
    expect(await screen.findByRole("alert")).not.toHaveTextContent("private");
    expect(
      screen.queryByRole("button", { name: /Revoke/ }),
    ).not.toBeInTheDocument();
  },
);
