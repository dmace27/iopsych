import { afterEach, expect, it, vi } from "vitest";
import { issueInvitation } from "./invitation-issuance-client";
import { InvitationCreateSchema } from "./invitation-issuance-contracts";
const input = {
  role_profile_id: "00000000-0000-4000-8000-000000000002",
  email: "synthetic@example.invalid",
};
const invite = {
  ...input,
  id: "00000000-0000-4000-8000-000000000001",
  status: "pending_delivery",
  created_at: "2026-11-04T12:00:00Z",
  expires_at: "2026-11-05T12:00:00Z",
  sent_at: null,
  revoked_at: null,
};
afterEach(() => vi.unstubAllGlobals());
it.each(["pending_delivery", "active"])(
  "posts strict payload and exact request key, accepting %s",
  async (status) => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          Response.json({ ...invite, status }, { status: 201 }),
        ),
    );
    expect((await issueInvitation("role/id", input, "random-key")).status).toBe(
      status,
    );
    expect(fetch).toHaveBeenCalledWith(
      "/api/internal/roles/role%2Fid/invites",
      {
        method: "POST",
        cache: "no-store",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
          "Idempotency-Key": "random-key",
        },
        body: JSON.stringify(input),
      },
    );
  },
);
it("matches expiry and email limits and forbids extra request fields", () => {
  for (const value of [0, 721, 1.5])
    expect(
      InvitationCreateSchema.safeParse({ ...input, expires_in_hours: value })
        .success,
    ).toBe(false);
  for (const value of [1, 720, null])
    expect(
      InvitationCreateSchema.safeParse({ ...input, expires_in_hours: value })
        .success,
    ).toBe(true);
  expect(
    InvitationCreateSchema.safeParse({ ...input, consent: true }).success,
  ).toBe(false);
  expect(
    InvitationCreateSchema.safeParse({ ...input, email: "invalid" }).success,
  ).toBe(false);
});
it.each([401, 403, 404, 409, 422, 429, 503])(
  "suppresses upstream details for %s",
  async (status) => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          Response.json({ detail: "private-token" }, { status }),
        ),
    );
    await expect(issueInvitation("role", input, "key")).rejects.toMatchObject({
      message: "The invitation request could not be completed.",
      status,
    });
  },
);
it("rejects unexpected success status and token-bearing responses", async () => {
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValueOnce(Response.json(invite))
      .mockResolvedValueOnce(
        Response.json({ ...invite, token: "private" }, { status: 201 }),
      )
      .mockRejectedValueOnce(new Error("private")),
  );
  for (let i = 0; i < 3; i++)
    await expect(issueInvitation("role", input, "key")).rejects.toThrow(
      "Invitation outcome is unknown",
    );
});
