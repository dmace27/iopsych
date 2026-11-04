// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { ApiClientError } from "../../../../lib/api-client";
import { ProviderDelivery } from "./provider-delivery";

const api = vi.hoisted(() => ({
  getInvitationDelivery: vi.fn(),
  reissueInvitation: vi.fn(),
}));
vi.mock("../../../../lib/api-client", async (original) => ({
  ...(await original<typeof import("../../../../lib/api-client")>()),
  ...api,
}));
const invitation = {
  id: "00000000-0000-4000-8000-000000000001",
  role_profile_id: "00000000-0000-4000-8000-000000000002",
  email: "synthetic@example.invalid",
  status: "revoked" as const,
  created_at: "2026-11-04T12:00:00Z",
  expires_at: "2026-11-05T12:00:00Z",
  sent_at: null,
  revoked_at: null,
};
const delivery = {
  id: "00000000-0000-4000-8000-000000000003",
  invite_id: invitation.id,
  status: "failed",
  attempt_count: 1,
  next_attempt_at: invitation.created_at,
  retry_until: invitation.expires_at,
  last_error_code: null,
};
afterEach(() => {
  cleanup();
  vi.resetAllMocks();
  vi.restoreAllMocks();
});
it("preserves local UI when provider has no record", async () => {
  api.getInvitationDelivery.mockRejectedValue(
    new ApiClientError("", { status: 404, code: "not_found" }),
  );
  render(
    <ProviderDelivery
      roleId="role"
      invitation={invitation}
      archived={false}
      disabled={false}
      onReissued={vi.fn()}
      onBusyChange={vi.fn()}
    />,
  );
  await userEvent.click(screen.getByText("Check provider delivery"));
  expect(
    await screen.findByText(
      /Local delivery and invitation history remain available/,
    ),
  ).toBeVisible();
  expect(screen.queryByText("Reissue invitation")).not.toBeInTheDocument();
});
it("requires confirmation and retries unknown outcomes with the identical request UUID", async () => {
  api.getInvitationDelivery.mockResolvedValue(delivery);
  api.reissueInvitation
    .mockRejectedValueOnce(
      new ApiClientError("", { status: 0, code: "network_error" }),
    )
    .mockResolvedValueOnce({ ...invitation, id: "replacement" });
  const confirm = vi
    .spyOn(window, "confirm")
    .mockReturnValueOnce(false)
    .mockReturnValue(true);
  const onReissued = vi.fn();
  render(
    <ProviderDelivery
      roleId="role"
      invitation={invitation}
      archived={false}
      disabled={false}
      onReissued={onReissued}
      onBusyChange={vi.fn()}
    />,
  );
  await userEvent.click(screen.getByText("Check provider delivery"));
  await userEvent.click(await screen.findByText("Reissue invitation"));
  expect(api.reissueInvitation).not.toHaveBeenCalled();
  await userEvent.click(screen.getByText("Reissue invitation"));
  expect(
    await screen.findByText(/Replacement outcome is unknown/),
  ).toBeVisible();
  expect(api.reissueInvitation).toHaveBeenCalledTimes(1);
  await userEvent.click(screen.getByText("Retry same reissue request"));
  expect(api.reissueInvitation.mock.calls[0]).toEqual(
    api.reissueInvitation.mock.calls[1],
  );
  expect(api.reissueInvitation.mock.calls[0]![2].request_id).toMatch(
    /^[0-9a-f-]{36}$/,
  );
  expect(confirm).toHaveBeenCalledTimes(2);
  expect(onReissued).toHaveBeenCalledTimes(1);
});
it.each(["consented", "declined"] as const)(
  "never offers reissue for %s invitations",
  async (status) => {
    api.getInvitationDelivery.mockResolvedValue(delivery);
    render(
      <ProviderDelivery
        roleId="role"
        invitation={{ ...invitation, status }}
        archived={false}
        disabled={false}
        onReissued={vi.fn()}
        onBusyChange={vi.fn()}
      />,
    );
    await userEvent.click(screen.getByText("Check provider delivery"));
    expect(await screen.findByText(/Delivery failed/)).toBeVisible();
    expect(screen.queryByText("Reissue invitation")).not.toBeInTheDocument();
  },
);
it.each(["retrying", "delivered", "complained", "bounced"])(
  "does not replace %s delivery",
  async (status) => {
    api.getInvitationDelivery.mockResolvedValue({ ...delivery, status });
    render(
      <ProviderDelivery
        roleId="role"
        invitation={invitation}
        archived={false}
        disabled={false}
        onReissued={vi.fn()}
        onBusyChange={vi.fn()}
      />,
    );
    await userEvent.click(screen.getByText("Check provider delivery"));
    expect(await screen.findByText(status)).toBeVisible();
    expect(screen.queryByText("Reissue invitation")).not.toBeInTheDocument();
  },
);
