import { afterEach, expect, it, vi } from "vitest";
import { AccountPageSchema, AccountUpdateSchema } from "./account-contracts";
import { getAccounts, updateAccount } from "./account-client";

const account = {
  id: "10000000-0000-4000-8000-000000000099",
  email: "admin@alpha.example.invalid",
  name: "Alpha Admin",
  role: "admin",
  is_active: true,
  version: 1,
};
afterEach(() => vi.unstubAllGlobals());
it("accepts the backend fixture and rejects extra sensitive fields, duplicates and invalid updates", () => {
  expect(
    AccountPageSchema.parse({ items: [account], next_cursor: null }).items,
  ).toEqual([account]);
  expect(
    AccountPageSchema.safeParse({
      items: [{ ...account, auth_subject: "secret" }],
      next_cursor: null,
    }).success,
  ).toBe(false);
  expect(
    AccountPageSchema.safeParse({
      items: [account, account],
      next_cursor: null,
    }).success,
  ).toBe(false);
  expect(
    AccountUpdateSchema.parse({
      expected_version: 1,
      role: "hiring_manager",
      is_active: false,
    }).is_active,
  ).toBe(false);
  for (const input of [
    { expected_version: 1 },
    { expected_version: 0, role: "admin" },
    { expected_version: 1, role: null },
    { expected_version: 1, is_active: null },
  ])
    expect(AccountUpdateSchema.safeParse(input).success).toBe(false);
});
it("uses bounded pagination and versioned updates with no browser storage", async () => {
  const fetcher = vi
    .fn()
    .mockResolvedValueOnce(
      Response.json({ items: [account], next_cursor: null }),
    )
    .mockResolvedValueOnce(
      Response.json({ ...account, version: 2, is_active: false }),
    );
  vi.stubGlobal("fetch", fetcher);
  await getAccounts({ after: account.id });
  expect(fetcher.mock.calls[0][0]).toBe(
    `/api/internal/accounts/users?limit=25&after=${account.id}`,
  );
  await updateAccount(account.id, { expected_version: 1, is_active: false });
  expect(fetcher.mock.calls[1][1]).toMatchObject({
    method: "PATCH",
    cache: "no-store",
    body: JSON.stringify({ expected_version: 1, is_active: false }),
  });
  await expect(getAccounts({ limit: 101 })).rejects.toThrow();
  await expect(
    updateAccount("bad", { expected_version: 1, role: "admin" }),
  ).rejects.toThrow();
  expect(fetcher).toHaveBeenCalledTimes(2);
});
it.each([401, 403, 404, 409, 422, 500])(
  "normalizes %s without exposing upstream details",
  async (status) => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          Response.json(
            { code: "account_version_conflict", detail: "secret-auth-subject" },
            { status },
          ),
        ),
    );
    await expect(getAccounts()).rejects.toMatchObject({
      status,
      message: expect.not.stringContaining("secret-auth-subject"),
    });
  },
);
it("rejects stale successful responses and malformed pages", async () => {
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValueOnce(Response.json(account))
      .mockResolvedValueOnce(Response.json({ items: [], next_cursor: "bad" })),
  );
  await expect(
    updateAccount(account.id, { expected_version: 1, role: "recruiter" }),
  ).rejects.toMatchObject({ code: "invalid_api_response" });
  await expect(getAccounts()).rejects.toMatchObject({
    code: "invalid_api_response",
  });
});
it("handles last-admin conflicts and uncertain network outcomes safely", async () => {
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValueOnce(
        Response.json({ code: "last_active_admin" }, { status: 409 }),
      )
      .mockRejectedValueOnce(new Error("sensitive connection data")),
  );
  await expect(
    updateAccount(account.id, { expected_version: 1, is_active: false }),
  ).rejects.toMatchObject({
    code: "last_active_admin",
    message: expect.stringContaining("last active administrator"),
  });
  await expect(getAccounts()).rejects.toMatchObject({
    code: "network_error",
    message: expect.stringContaining("may have completed"),
  });
});
