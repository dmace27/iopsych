import { afterEach, expect, it, vi } from "vitest";
import { getInvitationDelivery, reissueInvitation } from "./api-client";
afterEach(() => vi.unstubAllGlobals());
it("validates provider delivery shape separately and rejects unsafe response extras", async () => {
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValue(Response.json({ status: "sent", token: "synthetic" })),
  );
  await expect(getInvitationDelivery("role", "invite")).rejects.toMatchObject({
    code: "invalid_api_response",
  });
  expect(fetch).toHaveBeenCalledWith(
    "/api/internal/roles/role/invites/invite/delivery",
    expect.objectContaining({ cache: "no-store" }),
  );
});
it("sends the stable reissue UUID and optional expiry without changing create adapters", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(Response.json({}, { status: 409 })),
  );
  const input = {
    request_id: "00000000-0000-4000-8000-000000000001",
    expires_in_hours: 24,
  };
  await expect(
    reissueInvitation("role", "invite", input),
  ).rejects.toMatchObject({ status: 409 });
  expect(fetch).toHaveBeenCalledWith(
    "/api/internal/roles/role/invites/invite/reissue",
    expect.objectContaining({ method: "POST", body: JSON.stringify(input) }),
  );
});
