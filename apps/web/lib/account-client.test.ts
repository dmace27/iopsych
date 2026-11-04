import { afterEach, expect, it, vi } from "vitest";
import { AccountPageSchema, AccountUpdateSchema } from "./account-contracts";
import { getAccounts, updateAccount } from "./account-client";
import pageFixture from "../../api/tests/fixtures/accounts/page.json";
import updateFixture from "../../api/tests/fixtures/accounts/update.json";

const account = AccountPageSchema.parse(pageFixture).items[0];
const canonicalUpdate = AccountUpdateSchema.parse(updateFixture);
afterEach(() => vi.unstubAllGlobals());
it("accepts the backend fixture and rejects extra sensitive fields, duplicates and invalid updates", () => {
  expect(
    AccountPageSchema.parse(pageFixture).items,
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
    canonicalUpdate.is_active,
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
it.each([
  { role: account.role },
  { is_active: true },
  { is_active: false },
  { role: canonicalUpdate.role, is_active: canonicalUpdate.is_active },
])("accepts unchanged-version no-ops matching %j", async (mutation) => {
  const response = { ...account, ...mutation };
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json(response)));
  await expect(
    updateAccount(account.id, { expected_version: account.version, ...mutation }),
  ).resolves.toEqual(response);
});
it.each([
  { role: canonicalUpdate.role },
  { is_active: false },
  { role: canonicalUpdate.role, is_active: false },
])("accepts one version increment matching %j", async (mutation) => {
  const response = { ...account, ...mutation, version: account.version + 1 };
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json(response)));
  await expect(
    updateAccount(account.id, { expected_version: account.version, ...mutation }),
  ).resolves.toEqual(response);
});
it.each([1, 2, 3, 4])(
  "rejects wrong identities and any mismatched mutation at version %s",
  async (version) => {
    const response = {
      ...account,
      role: canonicalUpdate.role,
      is_active: canonicalUpdate.is_active,
      version,
    };
    for (const invalid of [
      { ...response, id: "10000000-0000-4000-8000-000000000098" },
      { ...response, role: account.role },
      { ...response, is_active: account.is_active },
      { ...response, role: account.role, is_active: account.is_active },
    ]) {
      vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json(invalid)));
      await expect(
        updateAccount(account.id, { ...canonicalUpdate, expected_version: 2 }),
      ).rejects.toMatchObject({ code: "invalid_api_response" });
    }
  },
);
it.each([1, 4])(
  "rejects matching mutations at stale or skipped version %s",
  async (version) => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(Response.json({ ...account, version })),
    );
    await expect(
      updateAccount(account.id, {
        expected_version: 2,
        role: account.role,
        is_active: account.is_active,
      }),
    ).rejects.toMatchObject({ code: "invalid_api_response" });
  },
);
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
