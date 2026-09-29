import { CONSTRUCT_KEYS } from "@iopsych/shared";
import { describe, expect, it } from "vitest";

import {
  CurrentUserSchema,
  RoleProfileSchema,
  RoleSchema,
  type RoleConstructRating,
} from "./contracts";

const IDS = {
  organization: "11111111-1111-4111-8111-111111111111",
  profile: "22222222-2222-4222-8222-222222222222",
  role: "33333333-3333-4333-8333-333333333333",
  user: "44444444-4444-4444-8444-444444444444",
};

/** Create a complete rating collection that mirrors the version-one contract. */
function constructs(): RoleConstructRating[] {
  return CONSTRUCT_KEYS.map((key) => ({
    confidence: "high",
    evidence: [`Exact ${key} evidence`],
    key,
    rationale: `${key} rationale`,
    rating: 4,
  }));
}

describe("internal role UI contracts", () => {
  it("accepts the existing current-user and role response shapes", () => {
    expect(
      CurrentUserSchema.parse({
        email: "recruiter@example.test",
        id: IDS.user,
        name: "Synthetic Recruiter",
        organization_id: IDS.organization,
        role: "recruiter",
      }).role,
    ).toBe("recruiter");
    expect(
      RoleSchema.parse({
        created_at: "2026-09-26T12:00:00Z",
        department: "Product",
        id: IDS.role,
        job_description: "Work independently with product partners.",
        location: "Remote",
        organization_id: IDS.organization,
        status: "draft",
        title: "Product Engineer",
      }).status,
    ).toBe("draft");
  });

  it("accepts one complete immutable profile snapshot", () => {
    const profile = RoleProfileSchema.parse({
      approved_at: null,
      approved_by: null,
      assumptions: ["Team practices are not fully described."],
      constructs: constructs(),
      created_at: "2026-09-26T12:00:00Z",
      created_by: IDS.user,
      id: IDS.profile,
      role_id: IDS.role,
      status: "draft",
      version: 1,
    });

    expect(profile.constructs.map(({ key }) => key)).toEqual(CONSTRUCT_KEYS);
  });

  it("rejects duplicate constructs even when the list still has six items", () => {
    const duplicated = constructs();
    duplicated[5] = { ...duplicated[5]!, key: "autonomy" };

    const result = RoleProfileSchema.safeParse({
      approved_at: null,
      approved_by: null,
      assumptions: [],
      constructs: duplicated,
      created_at: "2026-09-26T12:00:00Z",
      created_by: IDS.user,
      id: IDS.profile,
      role_id: IDS.role,
      status: "draft",
      version: 1,
    });

    expect(result.success).toBe(false);
  });
});
