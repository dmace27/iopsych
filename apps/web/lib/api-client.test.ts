import { CONSTRUCT_KEYS } from "@iopsych/shared";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  ApiClientError,
  approveRoleProfile,
  createRole,
  createRoleProfile,
  extractRoleProfile,
  getCurrentUser,
  getRole,
  getRoleProfiles,
  getRoles,
  reviseRoleProfile,
} from "./api-client";
import type { RoleConstructRating, RoleProfile } from "./contracts";

const IDS = {
  organization: "11111111-1111-4111-8111-111111111111",
  profile: "22222222-2222-4222-8222-222222222222",
  role: "33333333-3333-4333-8333-333333333333",
  user: "44444444-4444-4444-8444-444444444444",
};

const role = {
  created_at: "2026-09-26T12:00:00Z",
  department: "Product",
  id: IDS.role,
  job_description: "Work independently with product partners.",
  location: "Remote",
  organization_id: IDS.organization,
  status: "draft" as const,
  title: "Product Engineer",
};

/** Produce the complete six-construct payload required by profile creation. */
function constructs(): RoleConstructRating[] {
  return CONSTRUCT_KEYS.map((key) => ({
    confidence: "high",
    evidence: [`Exact ${key} evidence`],
    key,
    rationale: `${key} rationale`,
    rating: 4,
  }));
}

/** Produce an API-valid immutable profile response for adapter tests. */
function profile(): RoleProfile {
  return {
    approved_at: null,
    approved_by: null,
    assumptions: [],
    constructs: constructs(),
    created_at: "2026-09-26T12:00:00Z",
    created_by: IDS.user,
    id: IDS.profile,
    role_id: IDS.role,
    status: "draft",
    version: 1,
  };
}

describe("role API client", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("loads current-user, role, and profile data from same-origin paths", async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(
        Response.json({
          email: "synthetic@example.test",
          id: IDS.user,
          name: "Synthetic Recruiter",
          organization_id: IDS.organization,
          role: "recruiter",
        }),
      )
      .mockResolvedValueOnce(Response.json([role]))
      .mockResolvedValueOnce(Response.json(role))
      .mockResolvedValueOnce(Response.json([profile()]));

    await expect(getCurrentUser()).resolves.toMatchObject({
      role: "recruiter",
    });
    await expect(getRoles()).resolves.toHaveLength(1);
    await expect(getRole(IDS.role)).resolves.toMatchObject({ id: IDS.role });
    await expect(getRoleProfiles(IDS.role)).resolves.toHaveLength(1);

    expect(vi.mocked(fetch).mock.calls.map(([path]) => path)).toEqual([
      "/api/internal/auth/me",
      "/api/internal/roles",
      `/api/internal/roles/${IDS.role}`,
      `/api/internal/roles/${IDS.role}/profiles`,
    ]);
  });

  it("sends extraction, create, revise, and approval to their exact API paths", async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(Response.json(role, { status: 201 }))
      .mockResolvedValueOnce(Response.json(profile(), { status: 201 }))
      .mockResolvedValueOnce(Response.json(profile(), { status: 201 }))
      .mockResolvedValueOnce(Response.json(profile()))
      .mockResolvedValueOnce(
        Response.json({
          ...profile(),
          approved_at: "2026-09-26T13:00:00Z",
          approved_by: IDS.user,
          status: "approved",
        }),
      );

    await createRole({
      department: role.department,
      job_description: role.job_description,
      location: role.location,
      title: role.title,
    });
    await extractRoleProfile(IDS.role);
    await createRoleProfile(IDS.role, { constructs: constructs() });
    await reviseRoleProfile(IDS.role, IDS.profile, {
      constructs: constructs(),
    });
    await approveRoleProfile(IDS.role, IDS.profile);

    const calls = vi.mocked(fetch).mock.calls;
    expect(calls.map(([path]) => path)).toEqual([
      "/api/internal/roles",
      `/api/internal/roles/${IDS.role}/extract-profile`,
      `/api/internal/roles/${IDS.role}/profiles`,
      `/api/internal/roles/${IDS.role}/profiles/${IDS.profile}`,
      `/api/internal/roles/${IDS.role}/profiles/${IDS.profile}/approve`,
    ]);
    expect(calls.map(([, init]) => init?.method)).toEqual([
      "POST",
      "POST",
      "POST",
      "PATCH",
      "POST",
    ]);
    expect(new Headers(calls[0]![1]?.headers).get("Content-Type")).toBe(
      "application/json",
    );
    expect(calls[1]![1]?.body).toBeUndefined();
    expect(calls[4]![1]?.body).toBeUndefined();
  });

  it("preserves problem details and field errors", async () => {
    vi.mocked(fetch).mockResolvedValue(
      Response.json(
        {
          code: "validation_failed",
          detail: "One or more fields are invalid.",
          errors: [
            {
              code: "too_short",
              message: "Enter a title.",
              pointer: "/title",
            },
          ],
          status: 422,
          title: "Validation failed",
          type: "about:blank",
        },
        { status: 422 },
      ),
    );

    const error = await getRoles().catch((reason: unknown) => reason);

    expect(error).toBeInstanceOf(ApiClientError);
    expect(error).toMatchObject({
      code: "validation_failed",
      fieldErrors: [{ pointer: "/title" }],
      message: "One or more fields are invalid.",
      status: 422,
    });
  });

  it("fails safely for malformed success and error responses", async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(Response.json({ unexpected: true }))
      .mockResolvedValueOnce(new Response("not-json", { status: 500 }));

    await expect(getRoles()).rejects.toMatchObject({
      code: "invalid_api_response",
      status: 200,
    });
    await expect(getRoles()).rejects.toMatchObject({
      code: "unexpected_response",
      status: 500,
    });
  });

  it("normalizes transport failures without exposing implementation details", async () => {
    vi.mocked(fetch).mockRejectedValue(new Error("private network detail"));

    await expect(getRoles()).rejects.toMatchObject({
      code: "network_error",
      message: "The API could not be reached. Try again.",
      status: 0,
    });
  });
});
