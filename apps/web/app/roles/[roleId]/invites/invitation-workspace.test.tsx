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

it("moves keyboard focus to the revoked card and continues to the next action", async () => {
  api.getInvitations.mockResolvedValue({
    items: [invite, { ...invite, id: "two", email: "second@example.invalid" }],
    next_cursor: null,
  });
  vi.spyOn(window, "confirm").mockReturnValue(true);
  const user = userEvent.setup();
  render(<InvitationWorkspace roleId="role" />);
  (
    await screen.findByRole("button", {
      name: `Revoke invitation for ${invite.email}`,
    })
  ).focus();
  await user.keyboard("{Enter}");
  const card = await screen.findByRole("listitem", {
    name: `${invite.email}: Revoked`,
  });
  expect(card).toHaveFocus();
  expect(card).toHaveAttribute("tabindex", "-1");
  expect(card).toHaveClass("focus:ring-2");
  await user.tab();
  expect(
    screen.getByRole("button", {
      name: "Revoke invitation for second@example.invalid",
    }),
  ).toHaveFocus();
});

it.each([null, "next-page"])(
  "handles keyboard pagination focus with next cursor %s",
  async (next_cursor) => {
    api.getInvitations
      .mockResolvedValueOnce({ items: [invite], next_cursor: "first-page" })
      .mockResolvedValueOnce({
        items: [
          invite,
          { ...invite, id: "two", email: "second@example.invalid" },
        ],
        next_cursor,
      });
    const user = userEvent.setup();
    render(<InvitationWorkspace roleId="role" />);
    const load = await screen.findByRole("button", {
      name: "Load more invitations",
    });
    load.focus();
    await user.keyboard("{Enter}");
    const card = await screen.findByRole("listitem", {
      name: "second@example.invalid: Active",
    });
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
    if (next_cursor === null) {
      expect(card).toHaveFocus();
      expect(card).toHaveClass("focus:ring-2");
      expect(load).not.toBeInTheDocument();
      await user.tab();
      expect(
        screen.getByRole("button", {
          name: "Revoke invitation for second@example.invalid",
        }),
      ).toHaveFocus();
    } else {
      expect(load).toHaveFocus();
      expect(load).toBeEnabled();
    }
  },
);

it.each([{ items: [] }, { items: [invite] }])(
  "focuses the visible status when the final page adds no rows (%j)",
  async ({ items }) => {
    api.getInvitations
      .mockResolvedValueOnce({ items: [invite], next_cursor: "last-page" })
      .mockResolvedValueOnce({ items, next_cursor: null });
    const user = userEvent.setup();
    render(<InvitationWorkspace roleId="role" />);
    (
      await screen.findByRole("button", { name: "Load more invitations" })
    ).focus();
    await user.keyboard("{Enter}");
    expect(screen.getByRole("status")).toHaveFocus();
    expect(screen.getByRole("status")).toHaveTextContent(
      `${items.length} more invitations loaded.`,
    );
    expect(screen.getByRole("status")).toBeVisible();
  },
);

it.each(["revoke", "page"])(
  "retains the keyboard trigger after a failed %s request",
  async (action) => {
    api.getInvitations
      .mockResolvedValueOnce({ items: [invite], next_cursor: "page" })
      .mockRejectedValue(new Error("synthetic failure"));
    api.revokeInvitation.mockRejectedValue(new Error("synthetic failure"));
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const user = userEvent.setup();
    render(<InvitationWorkspace roleId="role" />);
    const trigger = await screen.findByRole("button", {
      name:
        action === "revoke" ? /Revoke invitation for/ : "Load more invitations",
    });
    trigger.focus();
    await user.keyboard("{Enter}");
    expect(await screen.findByRole("alert")).toHaveTextContent("Try again");
    expect(trigger).toHaveFocus();
    expect(trigger).toBeEnabled();
    expect(screen.getByText("Active")).toBeVisible();
  },
);

it("retains keyboard focus when revocation is cancelled", async () => {
  vi.spyOn(window, "confirm").mockReturnValue(false);
  const user = userEvent.setup();
  render(<InvitationWorkspace roleId="role" />);
  const revoke = await screen.findByRole("button", {
    name: /Revoke invitation for/,
  });
  revoke.focus();
  await user.keyboard("{Enter}");
  expect(revoke).toHaveFocus();
  expect(api.revokeInvitation).not.toHaveBeenCalled();
});

it("does not steal focus when the user moves during revocation", async () => {
  let finish!: (value: unknown) => void;
  api.revokeInvitation.mockImplementation(
    () =>
      new Promise((resolve) => {
        finish = resolve;
      }),
  );
  vi.spyOn(window, "confirm").mockReturnValue(true);
  const user = userEvent.setup();
  render(<InvitationWorkspace roleId="role" />);
  (
    await screen.findByRole("button", { name: /Revoke invitation for/ })
  ).focus();
  await user.keyboard("{Enter}");
  const back = screen.getByRole("link", { name: /Back to role profile/ });
  back.focus();
  finish({ ...invite, status: "revoked" });
  await screen.findByText("Revoked", { exact: true });
  expect(back).toHaveFocus();
});

it.each(["revoke", "page"])(
  "ignores late %s focus work after a role switch",
  async (action) => {
    let finish!: (value: unknown) => void;
    const pending = new Promise((resolve) => {
      finish = resolve;
    });
    api.getInvitations.mockResolvedValueOnce({
      items: [invite],
      next_cursor: "page",
    });
    if (action === "revoke") api.revokeInvitation.mockReturnValueOnce(pending);
    else api.getInvitations.mockReturnValueOnce(pending);
    api.getInvitations.mockResolvedValue({ items: [], next_cursor: null });
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const user = userEvent.setup();
    const view = render(<InvitationWorkspace roleId="old" />);
    (
      await screen.findByRole("button", {
        name:
          action === "revoke"
            ? /Revoke invitation for/
            : "Load more invitations",
      })
    ).focus();
    await user.keyboard("{Enter}");
    view.rerender(<InvitationWorkspace roleId="new" />);
    await screen.findByText("No invitations yet");
    const back = screen.getByRole("link", { name: /Back to role profile/ });
    back.focus();
    finish(
      action === "revoke"
        ? { ...invite, status: "revoked" }
        : { items: [invite], next_cursor: null },
    );
    await waitFor(() =>
      expect(screen.getByText("No invitations yet")).toBeVisible(),
    );
    expect(back).toHaveFocus();
    expect(screen.queryByText(invite.email)).not.toBeInTheDocument();
  },
);
