import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { GET, POST } from "./route";

const ORIGINAL_API_BASE_URL = process.env.API_BASE_URL;

function context(...path: string[]) {
  return { params: Promise.resolve({ path }) };
}

describe("candidate API proxy", () => {
  beforeEach(() => {
    delete process.env.API_BASE_URL;
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    if (ORIGINAL_API_BASE_URL === undefined) delete process.env.API_BASE_URL;
    else process.env.API_BASE_URL = ORIGINAL_API_BASE_URL;
  });

  it("forwards the package 2B invitation read without internal credentials", async () => {
    const upstream = new Response(
      JSON.stringify({ invitation_id: "safe-response" }),
    );
    upstream.headers.delete("Content-Type");
    vi.mocked(fetch).mockResolvedValue(upstream);

    const response = await GET(
      new Request("http://web.test/api/candidate/invites/raw.token"),
      context("raw.token"),
    );

    expect(response.status).toBe(200);
    expect(fetch).toHaveBeenCalledWith(
      new URL("http://localhost:8000/v1/candidate/invites/raw.token"),
      expect.objectContaining({ cache: "no-store", method: "GET" }),
    );
    const [, init] = vi.mocked(fetch).mock.calls[0]!;
    expect(new Headers(init?.headers).has("Authorization")).toBe(false);
    expect(response.headers.get("Content-Type")).toBe("application/json");
  });

  it("forwards a same-origin consent decision and content type", async () => {
    vi.mocked(fetch).mockResolvedValue(Response.json({ decision: "consent" }));
    const request = new Request(
      "http://web.test/api/candidate/invites/raw.token/consent",
      {
        body: JSON.stringify({ decision: "consent" }),
        headers: {
          "Content-Type": "application/json",
          Origin: "http://web.test",
        },
        method: "POST",
      },
    );

    await POST(request, context("raw.token", "consent"));

    const [url, init] = vi.mocked(fetch).mock.calls[0]!;
    expect(String(url)).toBe(
      "http://localhost:8000/v1/candidate/invites/raw.token/consent",
    );
    expect(new Headers(init?.headers).get("Content-Type")).toBe(
      "application/json",
    );
    expect(new TextDecoder().decode(init?.body as ArrayBuffer)).toBe(
      JSON.stringify({ decision: "consent" }),
    );
  });

  it("rejects cross-site consent before contacting the API", async () => {
    const response = await POST(
      new Request("http://web.test/api/candidate/invites/token/consent", {
        headers: { Origin: "https://attacker.example" },
        method: "POST",
      }),
      context("token", "consent"),
    );

    expect(response.status).toBe(403);
    expect(fetch).not.toHaveBeenCalled();
  });

  it("does not turn the anonymous proxy into an open API forwarder", async () => {
    const response = await GET(
      new Request("http://web.test/api/candidate/invites/token/assessment"),
      context("token", "assessment"),
    );

    expect(response.status).toBe(404);
    expect(fetch).not.toHaveBeenCalled();
  });

  it("returns a stable problem when the API is unavailable", async () => {
    vi.mocked(fetch).mockRejectedValue(new Error("private network detail"));

    const response = await GET(
      new Request("http://web.test/api/candidate/invites/token"),
      context("token"),
    );

    expect(response.status).toBe(502);
    await expect(response.json()).resolves.toMatchObject({
      code: "api_unavailable",
      status: 502,
    });
  });

  it("forwards a same-origin submission without internal credentials and rejects cross-site submissions", async () => {
    vi.mocked(fetch).mockResolvedValue(
      Response.json({ assessment_id: "receipt" }),
    );
    const payload = JSON.stringify({ responses: [] });
    const response = await POST(
      new Request("http://web.test/api/candidate/invites/token/submit", {
        method: "POST",
        headers: {
          Origin: "http://web.test",
          "Content-Type": "application/json",
        },
        body: payload,
      }),
      context("token", "submit"),
    );
    expect(response.headers.get("Cache-Control")).toBe("no-store");
    const [url, init] = vi.mocked(fetch).mock.calls[0]!;
    expect(String(url)).toBe(
      "http://localhost:8000/v1/candidate/invites/token/submit",
    );
    expect(new Headers(init?.headers).has("Authorization")).toBe(false);
    expect(new TextDecoder().decode(init?.body as ArrayBuffer)).toBe(payload);
    vi.mocked(fetch).mockClear();
    const denied = await POST(
      new Request("http://web.test/api/candidate/invites/token/submit", {
        method: "POST",
        headers: { Origin: "https://attacker.example" },
      }),
      context("token", "submit"),
    );
    expect(denied.status).toBe(403);
    expect(fetch).not.toHaveBeenCalled();
  });
});
