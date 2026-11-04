import { afterEach, expect, it, vi } from "vitest";
const headers = vi.hoisted(() => ({ cookies: vi.fn() }));
vi.mock("next/headers", () => ({ cookies: headers.cookies }));
import { GET, PATCH, POST, DELETE } from "./route";
afterEach(() => vi.unstubAllGlobals());
it("allows only account list and UUID patch, preserves query/body and enforces CSRF", async () => {
  headers.cookies.mockResolvedValue({
    get: () => ({ value: "synthetic-session" }),
  });
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockImplementation(async () =>
        Response.json({ items: [], next_cursor: null }),
      ),
  );
  const id = "10000000-0000-4000-8000-000000000099";
  const ctx = (...path: string[]) => ({ params: Promise.resolve({ path }) });
  expect(
    (
      await GET(
        new Request(
          `http://web.test/api/internal/accounts/users?limit=25&after=${id}`,
        ),
        ctx("accounts", "users"),
      )
    ).status,
  ).toBe(200);
  expect(String(vi.mocked(fetch).mock.calls[0][0])).toMatch(
    new RegExp(`/v1/accounts/users\\?limit=25&after=${id}$`),
  );
  const body = JSON.stringify({ expected_version: 1, is_active: false });
  expect(
    (
      await PATCH(
        new Request("http://web.test/api/test", {
          method: "PATCH",
          headers: {
            Origin: "http://web.test",
            "Content-Type": "application/json",
          },
          body,
        }),
        ctx("accounts", "users", id),
      )
    ).status,
  ).toBe(200);
  expect(
    new TextDecoder().decode(
      vi.mocked(fetch).mock.calls[1][1]?.body as ArrayBuffer,
    ),
  ).toBe(body);
  for (const [handler, method, path] of [
    [POST, "POST", ["accounts", "users"]],
    [DELETE, "DELETE", ["accounts", "users", id]],
    [GET, "GET", ["accounts", "users", id]],
    [PATCH, "PATCH", ["accounts", "users"]],
    [PATCH, "PATCH", ["accounts", "users", "bad"]],
    [PATCH, "PATCH", ["accounts", "users", id, "extra"]],
  ] as const)
    expect(
      (
        await handler(
          new Request("http://web.test/api/test", {
            method,
            headers: { Origin: "http://web.test" },
          }),
          ctx(...path),
        )
      ).status,
    ).toBe(404);
  expect(
    (
      await PATCH(
        new Request("http://web.test/api/test", {
          method: "PATCH",
          headers: { Origin: "https://other.invalid" },
        }),
        ctx("accounts", "users", id),
      )
    ).status,
  ).toBe(403);
  expect(fetch).toHaveBeenCalledTimes(2);
});
