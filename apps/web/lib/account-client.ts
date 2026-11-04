import { z } from "zod";
import { ApiClientError } from "./api-client";
import {
  AccountSchema,
  AccountPageSchema,
  AccountQuerySchema,
  AccountUpdateSchema,
  type AccountUpdate,
} from "./account-contracts";

async function request(path: string, input?: AccountUpdate): Promise<unknown> {
  let response: Response;
  try {
    response = await fetch(`/api/internal/accounts/users${path}`, {
      method: input ? "PATCH" : "GET",
      cache: "no-store",
      headers: {
        Accept: "application/json",
        ...(input ? { "Content-Type": "application/json" } : {}),
      },
      ...(input ? { body: JSON.stringify(input) } : {}),
    });
  } catch {
    throw new ApiClientError(
      "Connection lost. Refresh accounts before trying another change; the request may have completed.",
      { status: 0, code: "network_error" },
    );
  }
  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const problem = z.object({ code: z.string() }).safeParse(payload);
    const code =
      problem.success &&
      ["account_version_conflict", "last_active_admin"].includes(
        problem.data.code,
      )
        ? problem.data.code
        : "account_request_failed";
    const messages: Record<number, string> = {
      401: "Your session has expired or access is disabled. Sign in again.",
      403: "Only administrators can manage other accounts. You cannot change your own account.",
      404: "This account or page is no longer available in your organization. Refresh accounts.",
      409:
        code === "last_active_admin"
          ? "The last active administrator cannot be removed. Refresh accounts before reviewing another change."
          : "Account details changed. Refresh accounts and review the latest values before trying again.",
      422: "The account change is invalid. Refresh accounts and review the fields.",
    };
    throw new ApiClientError(
      messages[response.status] ??
        "The request failed. Refresh accounts before trying another change.",
      { status: response.status, code },
    );
  }
  return payload;
}
function invalidResponse(): never {
  throw new ApiClientError(
    "The API returned unexpected account details. Refresh accounts before continuing.",
    { status: 200, code: "invalid_api_response" },
  );
}
export async function getAccounts(
  query: { limit?: number; after?: string } = {},
) {
  const input = AccountQuerySchema.parse(query);
  const params = new URLSearchParams({ limit: String(input.limit) });
  if (input.after) params.set("after", input.after);
  const parsed = AccountPageSchema.safeParse(await request(`?${params}`));
  if (
    !parsed.success ||
    parsed.data.items.length > input.limit ||
    (input.after && parsed.data.next_cursor === input.after)
  )
    return invalidResponse();
  return parsed.data;
}
export async function updateAccount(id: string, input: AccountUpdate) {
  const accountId = z.uuid().parse(id);
  const update = AccountUpdateSchema.parse(input);
  const parsed = AccountSchema.safeParse(
    await request(`/${accountId}`, update),
  );
  if (
    !parsed.success ||
    parsed.data.id !== accountId ||
    parsed.data.version <= update.expected_version
  )
    return invalidResponse();
  return parsed.data;
}
