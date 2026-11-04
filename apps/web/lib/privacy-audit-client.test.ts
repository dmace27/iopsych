import { afterEach, describe, expect, it, vi } from "vitest";

import { getPrivacyAuditEvents } from "./api-client";

describe("privacy audit request scope", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("requests related assessment history with its cursor and bounded page size", async () => {
    const fetchMock = vi.fn().mockResolvedValue(Response.json([]));
    vi.stubGlobal("fetch", fetchMock);
    const assessmentId = "11111111-1111-4111-8111-111111111111";
    const cursor = "22222222-2222-4222-8222-222222222222";
    await expect(
      getPrivacyAuditEvents({ assessment_id: assessmentId }, cursor, 25),
    ).resolves.toEqual([]);
    const url = new URL(
      fetchMock.mock.calls[0][0],
      "https://synthetic.example.test",
    );
    expect(url.pathname).toBe("/api/internal/privacy/audit-events");
    expect(Object.fromEntries(url.searchParams)).toEqual({
      assessment_id: assessmentId,
      before: cursor,
      limit: "25",
    });
  });

  it("keeps exact entity and organization-wide callers compatible", async () => {
    const fetchMock = vi
      .fn()
      .mockImplementation(() => Promise.resolve(Response.json([])));
    vi.stubGlobal("fetch", fetchMock);
    const entityId = "11111111-1111-4111-8111-111111111111";
    await getPrivacyAuditEvents(entityId);
    await getPrivacyAuditEvents();
    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      `/api/internal/privacy/audit-events?entity_id=${entityId}`,
      "/api/internal/privacy/audit-events",
    ]);
  });
});
