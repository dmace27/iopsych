import { afterEach, expect, it, vi } from "vitest";
import { InvitationSchema } from "./invitation-contracts";
import { getInvitations, revokeInvitation } from "./invitation-client";
import { issueInvitation } from "./invitation-issuance-client";

const invitation = {
  id: "00000000-0000-4000-8000-000000000001",
  role_profile_id: "00000000-0000-4000-8000-000000000002",
  email: "synthetic@example.invalid",
  status: "pending_delivery",
  created_at: "2026-11-04T12:00:00Z",
  expires_at: "2026-11-05T12:00:00Z",
  sent_at: null,
  revoked_at: null,
};
afterEach(() => vi.unstubAllGlobals());

it.each([
  undefined,
  null,
  "queued",
  "sending",
  "sent",
  "uncertain",
  "cancelled",
  "expired",
])(
  "accepts delivery state %s across create/list/revoke with unchanged invitation status",
  async (delivery_state) => {
    const response =
      delivery_state === undefined
        ? invitation
        : { ...invitation, delivery_state };
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(Response.json(response, { status: 201 }))
        .mockResolvedValueOnce(
          Response.json({ items: [response], next_cursor: null }),
        )
        .mockResolvedValueOnce(Response.json(response)),
    );
    expect(
      await issueInvitation(
        "role",
        {
          role_profile_id: invitation.role_profile_id,
          email: invitation.email,
        },
        "synthetic-key",
      ),
    ).toEqual(response);
    expect((await getInvitations("role")).items).toEqual([response]);
    expect(await revokeInvitation("role", invitation.id)).toEqual(response);
    expect(fetch).toHaveBeenCalledTimes(3);
  },
);

it.each(["delivered", "failed", "retrying", "", 1, {}, []])(
  "rejects unapproved delivery state %j",
  (delivery_state) => {
    expect(
      InvitationSchema.safeParse({ ...invitation, delivery_state }).success,
    ).toBe(false);
  },
);
it.each([
  "token",
  "credential",
  "idempotency_key",
  "recipient",
  "delivery_metadata",
])("still rejects extra %s information", (field) => {
  expect(
    InvitationSchema.safeParse({
      ...invitation,
      delivery_state: "queued",
      [field]: "synthetic-private",
    }).success,
  ).toBe(false);
});
