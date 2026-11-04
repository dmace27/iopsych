import { ApiClientError } from "./api-client";
import { RoleSchema, type Role } from "./contracts";
import {
  RoleUpdateSchema,
  type RoleUpdateInput,
} from "./role-maintenance-contracts";

async function mutate(
  roleId: string,
  method: "PATCH" | "DELETE",
  input?: RoleUpdateInput,
): Promise<Response> {
  let response: Response;
  try {
    response = await fetch(
      `/api/internal/roles/${encodeURIComponent(roleId)}`,
      {
        method,
        cache: "no-store",
        headers: {
          Accept: "application/json",
          ...(input ? { "Content-Type": "application/json" } : {}),
        },
        ...(input ? { body: JSON.stringify(input) } : {}),
      },
    );
  } catch {
    throw new ApiClientError(
      "The API could not be reached. Check the role before retrying; the change may have completed.",
      { status: 0, code: "network_error" },
    );
  }
  if (!response.ok) {
    const messages: Record<number, string> = {
      401: "Your session has expired. Sign in again, then retry.",
      403: "Only administrators and recruiters can maintain roles. Refresh to check your access.",
      404: "This role is no longer available to your organization.",
      409: "This role cannot be changed in its current state. Refresh to check whether it was archived.",
      422: "Check the role fields: each must contain text within its length limit.",
    };
    throw new ApiClientError(
      messages[response.status] ??
        "The role request could not be completed. Check the role before retrying.",
      { status: response.status, code: "role_request_failed" },
    );
  }
  return response;
}
export async function updateRole(
  roleId: string,
  input: RoleUpdateInput,
): Promise<Role> {
  const response = await mutate(roleId, "PATCH", RoleUpdateSchema.parse(input));
  const parsed = RoleSchema.safeParse(await response.json().catch(() => null));
  if (!parsed.success || parsed.data.id !== roleId)
    throw new ApiClientError(
      "The API returned an unexpected role response. Refresh to check the role.",
      { status: response.status, code: "invalid_api_response" },
    );
  return parsed.data;
}
export async function archiveRole(roleId: string): Promise<void> {
  const response = await mutate(roleId, "DELETE");
  if (response.status !== 204)
    throw new ApiClientError(
      "The API did not confirm archival. Refresh to check the role.",
      { status: response.status, code: "invalid_api_response" },
    );
}
