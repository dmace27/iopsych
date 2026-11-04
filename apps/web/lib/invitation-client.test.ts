import { afterEach, expect, it, vi } from "vitest";
import { getInvitations, revokeInvitation } from "./invitation-client";
import { InvitationSchema, canManageInvitations } from "./invitation-contracts";
export const invite = {
  id: "00000000-0000-4000-8000-000000000001",
  role_profile_id: "00000000-0000-4000-8000-000000000002",
  email: "synthetic@example.invalid",
  status: "active",
  created_at: "2026-11-04T12:00:00Z",
  expires_at: "2026-11-05T12:00:00Z",
  sent_at: null,
  revoked_at: null,
};
afterEach(() => vi.unstubAllGlobals());
it("preserves exact cursors, null timestamps and no-store through the internal proxy", async () => {
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockImplementation(async () =>
        Response.json({ items: [invite], next_cursor: null }),
      ),
  );
  expect(await getInvitations("role/id", "opaque+/=")).toEqual({
    items: [invite],
    next_cursor: null,
  });
  expect(fetch).toHaveBeenCalledWith(
    "/api/internal/roles/role%2Fid/invites?limit=25&cursor=opaque%2B%2F%3D",
    expect.objectContaining({ cache: "no-store", method: "GET" }),
  );
});
it("posts only to revoke and accepts the returned stored state", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(Response.json({ ...invite, status: "revoked" })),
  );
  expect((await revokeInvitation("role", invite.id)).status).toBe("revoked");
  expect(fetch).toHaveBeenCalledWith(
    `/api/internal/roles/role/invites/${invite.id}/revoke`,
    expect.objectContaining({ method: "POST" }),
  );
});
it("rejects invented statuses and extra bearer fields", () => {
  for (const status of [
    "pending_delivery",
    "active",
    "consented",
    "declined",
    "revoked",
    "expired",
  ])
    expect(InvitationSchema.safeParse({ ...invite, status }).success).toBe(
      true,
    );
  expect(
    InvitationSchema.safeParse({ ...invite, status: "submitted" }).success,
  ).toBe(false);
  expect(
    InvitationSchema.safeParse({ ...invite, token: "secret" }).success,
  ).toBe(false);
  expect(canManageInvitations("admin")).toBe(true);
  expect(canManageInvitations("recruiter")).toBe(true);
  expect(canManageInvitations("hiring_manager")).toBe(false);
});
it.each([401, 403, 404, 422, 429, 500])(
  "does not expose upstream error content (%s)",
  async (status) => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        Response.json(
          {
            type: "about:blank",
            title: "secret",
            detail: "https://secret/token",
            status,
            code: "invalid_invitation_cursor",
          },
          { status },
        ),
      ),
    );
    await expect(getInvitations("role")).rejects.toMatchObject({
      status,
      message: "The invitation request could not be completed.",
      code: "invalid_invitation_cursor",
    });
  },
);
it("normalizes network and malformed response failures", async () => {
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockRejectedValueOnce(new Error("secret"))
      .mockResolvedValueOnce(Response.json({ token: "secret" })),
  );
  await expect(getInvitations("role")).rejects.toMatchObject({
    code: "network_error",
  });
  await expect(getInvitations("role")).rejects.toMatchObject({
    code: "invalid_api_response",
  });
});
