import { afterEach, describe, expect, it, vi } from "vitest";
import { archiveRole, updateRole } from "./role-maintenance-client";
import {
  canMaintainRole,
  RoleUpdateSchema,
} from "./role-maintenance-contracts";

export const roleFixture = {
  id: "55555555-5555-4555-8555-555555555555",
  organization_id: "22222222-2222-4222-8222-222222222222",
  title: "Engineer",
  department: "Engineering",
  location: "Toronto",
  job_description: "Maintain services.",
  status: "active" as const,
  created_at: "2026-09-26T12:00:00Z",
};
afterEach(() => vi.unstubAllGlobals());
describe("existing role maintenance contract", () => {
  it("accepts trimmed partial fields at exact bounds", () => {
    expect(RoleUpdateSchema.parse({ title: "  Engineer  " })).toEqual({
      title: "Engineer",
    });
    expect(
      RoleUpdateSchema.safeParse({
        title: "a".repeat(160),
        department: "b".repeat(160),
        location: "c".repeat(160),
        job_description: "d".repeat(100000),
      }).success,
    ).toBe(true);
  });
  it.each([
    {},
    { title: null },
    { title: " " },
    { title: "a".repeat(161) },
    { department: "a".repeat(161) },
    { location: "a".repeat(161) },
    { job_description: "a".repeat(100001) },
    { status: "archived" },
    { title: undefined },
  ])("rejects invalid patches %#", (patch) =>
    expect(RoleUpdateSchema.safeParse(patch).success).toBe(false),
  );
  it("limits maintenance to existing permissions", () => {
    expect(canMaintainRole("admin")).toBe(true);
    expect(canMaintainRole("recruiter")).toBe(true);
    expect(canMaintainRole("hiring_manager")).toBe(false);
  });
  it("sends exact PATCH and validates exact response fixture", async () => {
    const fetcher = vi.fn().mockResolvedValue(Response.json(roleFixture));
    vi.stubGlobal("fetch", fetcher);
    expect(await updateRole(roleFixture.id, { title: " Engineer " })).toEqual(
      roleFixture,
    );
    expect(fetcher).toHaveBeenCalledWith(
      `/api/internal/roles/${roleFixture.id}`,
      {
        method: "PATCH",
        cache: "no-store",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: '{"title":"Engineer"}',
      },
    );
  });
  it("accepts a bodyless 204 archive", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetcher);
    await expect(archiveRole(roleFixture.id)).resolves.toBeUndefined();
    expect(fetcher).toHaveBeenCalledWith(
      `/api/internal/roles/${roleFixture.id}`,
      {
        method: "DELETE",
        cache: "no-store",
        headers: { Accept: "application/json" },
      },
    );
  });
  it.each([401, 403, 404, 409, 422, 500])(
    "normalizes %i without exposing raw content",
    async (status) => {
      vi.stubGlobal(
        "fetch",
        vi.fn().mockResolvedValue(new Response("secret upstream", { status })),
      );
      await expect(
        updateRole(roleFixture.id, { title: "New" }),
      ).rejects.toMatchObject({ status });
      await expect(archiveRole(roleFixture.id)).rejects.not.toThrow(
        "secret upstream",
      );
    },
  );
  it("handles uncertain network failures", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("secret")));
    await expect(archiveRole(roleFixture.id)).rejects.toMatchObject({
      status: 0,
    });
  });
  it("rejects malformed success and unconfirmed archive", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json({})));
    await expect(
      updateRole(roleFixture.id, { title: "New" }),
    ).rejects.toMatchObject({ code: "invalid_api_response" });
    await expect(archiveRole(roleFixture.id)).rejects.toMatchObject({
      code: "invalid_api_response",
    });
  });
});
