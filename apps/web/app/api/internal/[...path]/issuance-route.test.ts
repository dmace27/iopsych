import { afterEach, beforeEach, expect, it, vi } from "vitest";

const session = vi.hoisted(() => ({ cookies: vi.fn() }));
vi.mock("next/headers", () => ({ cookies: session.cookies }));
import { GET, POST } from "./route";

const roleId = "10000000-0000-4000-8000-000000000099";
const path = ["roles", roleId, "invites"];
const context = (segments = path) => ({
  params: Promise.resolve({ path: segments }),
});
const payload = JSON.stringify({
  role_profile_id: "20000000-0000-4000-8000-000000000099",
  email: "candidate@example.test",
  expires_in_hours: 720,
});
const request = (headers: Record<string, string> = {}, body = payload) =>
  new Request(`http://web.test/api/internal/roles/${roleId}/invites`, {
    method: "POST",
    headers: {
      Origin: "http://web.test",
      "Content-Type": "application/json",
      ...headers,
    },
    body,
  });

beforeEach(() => {
  session.cookies.mockReset();
  session.cookies.mockResolvedValue({
    get: () => ({ value: "synthetic-session" }),
    delete: vi.fn(),
  });
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(Response.json({ id: roleId }, { status: 201 })),
  );
});
afterEach(() => vi.unstubAllGlobals());

it.each(["Abcdef0123456789", "Z".repeat(128), "retry:AbcDEF-0123_!~"])(
  "forwards issuance and a valid key unchanged: %s",
  async (key) => {
    const response = await POST(
      request({
        "Idempotency-Key": key,
        Authorization: "Bearer attacker",
        Cookie: "unrelated=secret",
        "X-Forwarded-Host": "attacker.invalid",
        "X-Untrusted": "ignored",
      }),
      context(),
    );
    expect(response.status).toBe(201);
    expect(response.headers.get("Cache-Control")).toBe("no-store");
    expect(await response.json()).toEqual({ id: roleId });
    const [url, init] = vi.mocked(fetch).mock.calls[0]!;
    expect(new URL(String(url)).pathname).toBe(`/v1/roles/${roleId}/invites`);
    expect(init?.method).toBe("POST");
    expect(init?.cache).toBe("no-store");
    expect(new TextDecoder().decode(init?.body as ArrayBuffer)).toBe(payload);
    expect(Object.fromEntries(new Headers(init?.headers))).toEqual({
      accept: "application/json",
      authorization: "Bearer synthetic-session",
      "content-type": "application/json",
      "idempotency-key": key,
    });
  },
);

it.each([
  "",
  "x".repeat(15),
  "x".repeat(129),
  "has spaces in key",
  "nonascii-é-123456",
  "internal\ttab-123456",
])("rejects invalid keys before upstream fetch: %s", async (key) => {
  const response = await POST(request({ "Idempotency-Key": key }), context());
  expect(response.status).toBe(422);
  expect(response.headers.get("Cache-Control")).toBe("no-store");
  expect(await response.json()).toMatchObject({
    code: "invalid_idempotency_key",
  });
  expect(fetch).not.toHaveBeenCalled();
});

it.each([
  ["roles", "not-a-uuid", "invites"],
  ["roles", `${roleId}/extra`, "invites"],
  ["roles", `${roleId}%2fextra`, "invites"],
  ["roles", "..", "invites"],
  ["roles", roleId, "invites", "extra"],
  ["roles", roleId, "invites/extra"],
])("rejects non-exact issuance path %j", async (...segments) => {
  expect((await POST(request(), context(segments))).status).toBe(404);
  expect(fetch).not.toHaveBeenCalled();
});

it("rejects hostile origin before reading the session", async () => {
  const response = await POST(
    request({ Origin: "https://hostile.invalid" }),
    context(),
  );
  expect(response.status).toBe(403);
  expect(response.headers.get("Cache-Control")).toBe("no-store");
  expect(session.cookies).not.toHaveBeenCalled();
  expect(fetch).not.toHaveBeenCalled();
});

it("requires a session", async () => {
  session.cookies.mockResolvedValue({ get: () => undefined });
  const response = await POST(request(), context());
  expect(response.status).toBe(401);
  expect(response.headers.get("Cache-Control")).toBe("no-store");
  expect(fetch).not.toHaveBeenCalled();
});

it.each([400, 401, 403, 409, 422, 429, 503])(
  "preserves API error %i and leaves body/missing-key validation to API",
  async (status) => {
    const error = JSON.stringify({
      code: "api_validation_or_delivery_error",
      detail: "Synthetic failure",
    });
    vi.mocked(fetch).mockResolvedValue(
      new Response(error, {
        status,
        headers: {
          "Content-Type": "application/problem+json",
          "Retry-After": "30",
          "Set-Cookie": "upstream=hidden",
        },
      }),
    );
    const invalidBody = JSON.stringify({
      role_profile_id: "invalid",
      email: "invalid",
      expires_in_hours: 721,
      extra: true,
    });
    const response = await POST(request({}, invalidBody), context());
    expect(response.status).toBe(status);
    expect(await response.text()).toBe(error);
    expect(response.headers.get("Content-Type")).toBe(
      "application/problem+json",
    );
    expect(response.headers.get("Cache-Control")).toBe("no-store");
    expect(response.headers.get("Retry-After")).toBe("30");
    expect(response.headers.has("Set-Cookie")).toBe(false);
    const init = vi.mocked(fetch).mock.calls[0]![1];
    expect(new Headers(init?.headers).has("Idempotency-Key")).toBe(false);
    expect(new TextDecoder().decode(init?.body as ArrayBuffer)).toBe(
      invalidBody,
    );
  },
);

it("keeps GET invites and other POST routes from forwarding idempotency headers", async () => {
  await GET(
    new Request(
      `http://web.test/api/internal/roles/${roleId}/invites?limit=25`,
      {
        headers: { "Idempotency-Key": "invalid" },
      },
    ),
    context(),
  );
  await POST(
    request({ "Idempotency-Key": "invalid" }),
    context(["roles", roleId, "invites", roleId, "revoke"]),
  );
  expect(String(vi.mocked(fetch).mock.calls[0]![0])).toContain(
    "/invites?limit=25",
  );
  for (const [, init] of vi.mocked(fetch).mock.calls) {
    expect(new Headers(init?.headers).has("Idempotency-Key")).toBe(false);
  }
});

it("returns a non-cacheable gateway error for upstream transport failure", async () => {
  vi.mocked(fetch).mockRejectedValue(new Error("private upstream details"));
  const response = await POST(request(), context());
  expect(response.status).toBe(502);
  expect(response.headers.get("Cache-Control")).toBe("no-store");
  expect(await response.json()).toMatchObject({ code: "api_unavailable" });
});

it("keeps empty upstream responses non-cacheable", async () => {
  vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 204 }));
  const response = await POST(request(), context());
  expect(response.status).toBe(204);
  expect(await response.text()).toBe("");
  expect(response.headers.get("Cache-Control")).toBe("no-store");
});
