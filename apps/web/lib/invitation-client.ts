import { ApiProblemSchema } from "@iopsych/shared";
import type { z } from "zod";
import { ApiClientError } from "./api-client";
import { InvitationListSchema, InvitationSchema } from "./invitation-contracts";

async function request<T>(
  path: string,
  schema: z.ZodType<T>,
  method = "GET",
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api/internal${path}`, {
      method,
      cache: "no-store",
      headers: { Accept: "application/json" },
    });
  } catch {
    throw new ApiClientError("Invitations could not be reached. Try again.", {
      status: 0,
      code: "network_error",
    });
  }
  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const problem = ApiProblemSchema.safeParse(payload);
    // Never propagate upstream detail, instance, field errors, or credentials.
    throw new ApiClientError("The invitation request could not be completed.", {
      status: response.status,
      code:
        problem.success && problem.data.code === "invalid_invitation_cursor"
          ? "invalid_invitation_cursor"
          : "invitation_request_failed",
    });
  }
  const parsed = schema.safeParse(payload);
  if (!parsed.success)
    throw new ApiClientError(
      "The API returned an unexpected invitation response.",
      { status: response.status, code: "invalid_api_response" },
    );
  return parsed.data;
}

export function getInvitations(roleId: string, cursor?: string) {
  const query = new URLSearchParams({ limit: "25" });
  if (cursor !== undefined) query.set("cursor", cursor);
  return request(
    `/roles/${encodeURIComponent(roleId)}/invites?${query}`,
    InvitationListSchema,
  );
}
export function revokeInvitation(roleId: string, invitationId: string) {
  return request(
    `/roles/${encodeURIComponent(roleId)}/invites/${encodeURIComponent(invitationId)}/revoke`,
    InvitationSchema,
    "POST",
  );
}
