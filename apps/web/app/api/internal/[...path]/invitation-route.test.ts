import { afterEach, expect, it, vi } from "vitest";
const headers = vi.hoisted(() => ({ cookies: vi.fn() }));
vi.mock("next/headers", () => ({ cookies: headers.cookies }));
import { GET, POST, DELETE } from "./route";
afterEach(() => vi.unstubAllGlobals());
it("allows invitation list/revoke, preserves pagination and rejects create/extra paths/cross-site revoke", async () => {
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
  const ctx = (...path: string[]) => ({ params: Promise.resolve({ path }) });
  const response = await GET(
    new Request(
      "http://web.test/api/internal/roles/r/invites?limit=25&cursor=opaque",
    ),
    ctx("roles", "r", "invites"),
  );
  expect(response.status).toBe(200);
  expect(response.headers.get("Cache-Control")).toBe("no-store");
  expect(String(vi.mocked(fetch).mock.calls[0]![0])).toMatch(
    /\/v1\/roles\/r\/invites\?limit=25&cursor=opaque$/,
  );
  expect(
    (
      await POST(
        new Request("http://web.test/api/internal/roles/r/invites/i/revoke", {
          method: "POST",
          headers: { Origin: "http://web.test" },
        }),
        ctx("roles", "r", "invites", "i", "revoke"),
      )
    ).status,
  ).toBe(200);
  for (const [handler, method, path] of [
    [POST, "POST", ["roles", "r", "invites"]],
    [GET, "GET", ["roles", "r", "invites", "i", "revoke"]],
    [DELETE, "DELETE", ["roles", "r", "invites", "i"]],
    [GET, "GET", ["roles", "r", "invites", "extra"]],
  ] as const) {
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
  }
  expect(
    (
      await POST(
        new Request("http://web.test/api/test", {
          method: "POST",
          headers: { Origin: "https://other.invalid" },
        }),
        ctx("roles", "r", "invites", "i", "revoke"),
      )
    ).status,
  ).toBe(403);
  expect(fetch).toHaveBeenCalledTimes(2);
});

it("allows provider delivery and same-origin reissue while denying wrong methods and cross-site mutations", async () => {
  headers.cookies.mockResolvedValue({
    get: () => ({ value: "synthetic-session" }),
  });
  vi.stubGlobal(
    "fetch",
    vi.fn().mockImplementation(async () => Response.json({})),
  );
  const context = (action: string) => ({
    params: Promise.resolve({ path: ["roles", "r", "invites", "i", action] }),
  });
  expect(
    (await GET(new Request("http://web.test/api/test"), context("delivery")))
      .status,
  ).toBe(200);
  const body = JSON.stringify({
    request_id: "00000000-0000-4000-8000-000000000001",
  });
  expect(
    (
      await POST(
        new Request("http://web.test/api/test", {
          method: "POST",
          headers: {
            Origin: "http://web.test",
            "Content-Type": "application/json",
          },
          body,
        }),
        context("reissue"),
      )
    ).status,
  ).toBe(200);
  expect(
    new TextDecoder().decode(
      vi.mocked(fetch).mock.calls[1]![1]!.body as ArrayBuffer,
    ),
  ).toBe(body);
  expect(
    (await GET(new Request("http://web.test/api/test"), context("reissue")))
      .status,
  ).toBe(404);
  expect(
    (
      await POST(
        new Request("http://web.test/api/test", {
          method: "POST",
          headers: { Origin: "https://other.invalid" },
          body,
        }),
        context("reissue"),
      )
    ).status,
  ).toBe(403);
  expect(fetch).toHaveBeenCalledTimes(2);
});
