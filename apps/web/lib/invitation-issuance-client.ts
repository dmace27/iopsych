import { ApiClientError } from "./api-client";
import { InvitationSchema } from "./invitation-contracts";
import {
  InvitationCreateSchema,
  type InvitationCreate,
} from "./invitation-issuance-contracts";

export async function issueInvitation(
  roleId: string,
  input: InvitationCreate,
  key: string,
) {
  const body = InvitationCreateSchema.parse(input);
  let response: Response;
  try {
    response = await fetch(
      `/api/internal/roles/${encodeURIComponent(roleId)}/invites`,
      {
        method: "POST",
        cache: "no-store",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
          "Idempotency-Key": key,
        },
        body: JSON.stringify(body),
      },
    );
  } catch {
    throw new ApiClientError(
      "Invitation outcome is unknown. Check history before retrying.",
      { status: 0, code: "network_error" },
    );
  }
  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok)
    throw new ApiClientError("The invitation request could not be completed.", {
      status: response.status,
      code: "invitation_issuance_failed",
    });
  const parsed = InvitationSchema.safeParse(payload);
  if (response.status !== 201 || !parsed.success)
    throw new ApiClientError(
      "Invitation outcome is unknown. Check history before retrying.",
      { status: response.status, code: "invalid_api_response" },
    );
  return parsed.data;
}
