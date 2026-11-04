// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import {
  cleanup,
  render,
  screen,
  within,
  waitFor,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { InvitationWorkspace } from "./invitation-workspace";

const api = vi.hoisted(() => ({
  getCurrentUser: vi.fn(),
  getRole: vi.fn(),
  getInvitations: vi.fn(),
  revokeInvitation: vi.fn(),
  getRoleProfiles: vi.fn(),
  issueInvitation: vi.fn(),
}));
vi.mock("../../../../lib/api-client", async (original) => ({
  ...(await original<typeof import("../../../../lib/api-client")>()),
  getCurrentUser: api.getCurrentUser,
  getRole: api.getRole,
  getRoleProfiles: api.getRoleProfiles,
}));
vi.mock("../../../../lib/invitation-issuance-client", () => ({
  issueInvitation: api.issueInvitation,
}));
vi.mock("../../../../lib/invitation-client", () => ({
  getInvitations: api.getInvitations,
  revokeInvitation: api.revokeInvitation,
}));
const invitation = {
  id: "synthetic",
  role_profile_id: "profile",
  email: "synthetic@example.invalid",
  status: "pending_delivery",
  created_at: "2026-11-04T12:00:00Z",
  expires_at: "2026-11-05T12:00:00Z",
  sent_at: null,
  revoked_at: null,
};
beforeEach(() => {
  vi.resetAllMocks();
  api.getCurrentUser.mockResolvedValue({ role: "recruiter" });
  api.getRole.mockResolvedValue({
    title: "Synthetic role",
    status: "archived",
  });
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

it("blocks issuance during history refresh and allows history after an archive response", async () => {
  const profileId = "00000000-0000-4000-8000-000000000002";
  api.getRole.mockResolvedValueOnce({
    title: "Synthetic role",
    status: "active",
  });
  api.getRoleProfiles.mockResolvedValue([
    { id: profileId, version: 1, status: "approved" },
  ]);
  api.getInvitations.mockResolvedValue({ items: [], next_cursor: null });
  const user = userEvent.setup();
  render(<InvitationWorkspace roleId="role" />);
  await user.type(
    await screen.findByLabelText("Recipient email"),
    invitation.email,
  );
  await user.selectOptions(
    screen.getByLabelText("Approved profile version"),
    profileId,
  );
  await user.click(screen.getByRole("button", { name: "Review invitation" }));
  let finish!: (value: unknown) => void;
  api.getRole.mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        finish = resolve;
      }),
  );
  await user.click(
    screen.getByRole("button", { name: "Refresh invitation history" }),
  );
  const confirm = screen.getByRole("button", {
    name: "Confirm and issue invitation",
  });
  expect(confirm).toBeDisabled();
  await user.click(confirm);
  expect(api.issueInvitation).not.toHaveBeenCalled();
  finish({ title: "Synthetic role", status: "archived" });
  expect(
    await screen.findByText("Archived roles cannot issue invitations."),
  ).toBeVisible();
  await waitFor(() =>
    expect(
      screen.getByRole("button", { name: "Refresh invitation history" }),
    ).toBeEnabled(),
  );
});

it.each([
  ["queued", "Queued", "Waiting for a delivery attempt"],
  ["sending", "Sending", "A delivery attempt is in progress"],
  ["sent", "Sent", "Recipient receipt is not confirmed"],
  ["uncertain", "Delivery uncertain", "no automatic retry is pending"],
  ["cancelled", "Delivery cancelled", "No delivery work is pending"],
  ["expired", "Delivery expired", "No delivery work is pending"],
] as const)(
  "separates %s delivery from stored invitation state",
  async (delivery_state, label, guidance) => {
    api.getInvitations.mockResolvedValue({
      items: [{ ...invitation, delivery_state }],
      next_cursor: null,
    });
    render(<InvitationWorkspace roleId="role" />);
    const card = await screen.findByRole("listitem");
    expect(within(card).getByText("Pending delivery")).toBeVisible();
    expect(within(card).getByText(label, { exact: true })).toBeVisible();
    expect(card).toHaveTextContent(guidance);
    expect(api.revokeInvitation).not.toHaveBeenCalled();
    expect(api.getInvitations).toHaveBeenCalledTimes(1);
  },
);

it.each([undefined, null])(
  "does not infer delivery success for legacy %s",
  async (delivery_state) => {
    api.getInvitations.mockResolvedValue({
      items: [
        {
          ...invitation,
          status: "active",
          sent_at: invitation.created_at,
          delivery_state,
        },
      ],
      next_cursor: null,
    });
    render(<InvitationWorkspace roleId="role" />);
    const card = await screen.findByRole("listitem");
    expect(within(card).getByText("Active")).toBeVisible();
    expect(within(card).getByText("Unknown")).toBeVisible();
    expect(card).toHaveTextContent(
      "Legacy invitations may have used synchronous delivery",
    );
    expect(card).toHaveTextContent("do not confirm receipt");
  },
);

it.each(["uncertain", "expired", "cancelled"])(
  "requires explicit revoke for %s and retains focus",
  async (delivery_state) => {
    api.getInvitations.mockResolvedValue({
      items: [{ ...invitation, delivery_state }],
      next_cursor: null,
    });
    api.revokeInvitation.mockResolvedValue({
      ...invitation,
      status: "revoked",
      delivery_state: "cancelled",
    });
    const confirm = vi
      .spyOn(window, "confirm")
      .mockReturnValueOnce(false)
      .mockReturnValueOnce(true);
    const user = userEvent.setup();
    render(<InvitationWorkspace roleId="role" />);
    const revoke = await screen.findByRole("button", {
      name: /Revoke invitation for/,
    });
    expect(screen.getByRole("listitem")).toHaveTextContent(
      "explicitly revoke it first",
    );
    await user.click(revoke);
    expect(api.revokeInvitation).not.toHaveBeenCalled();
    await user.click(revoke);
    expect(await screen.findByText("Revoked", { exact: true })).toBeVisible();
    expect(screen.getByRole("listitem")).toHaveFocus();
    expect(screen.getByRole("listitem")).toHaveTextContent(
      "This invitation is revoked",
    );
    expect(confirm).toHaveBeenCalledTimes(2);
    expect(api.revokeInvitation).toHaveBeenCalledTimes(1);
  },
);
