import { CONSTRUCT_KEYS } from "@iopsych/shared";
import { describe, expect, it } from "vitest";

import type { RoleProfile } from "./contracts";
import {
  blankConstructs,
  canApproveProfiles,
  canEditProfiles,
  canEditRoles,
  formatDate,
  sortProfiles,
} from "./role-ui";

/** Build only the immutable fields needed to exercise history ordering. */
function profile(version: number): RoleProfile {
  return {
    approved_at: null,
    approved_by: null,
    constructs: blankConstructs().map((construct) => ({
      ...construct,
      evidence: ["Exact evidence"],
      rationale: "Reviewed rationale",
    })),
    created_at: "2026-09-26T12:00:00Z",
    created_by: "44444444-4444-4444-8444-444444444444",
    id: `${version}2222222-2222-4222-8222-222222222222`,
    role_id: "33333333-3333-4333-8333-333333333333",
    status: "draft",
    version,
  };
}

describe("role workspace presentation rules", () => {
  it("shows authoring controls only for API-authorized roles", () => {
    expect(canEditRoles("recruiter")).toBe(true);
    expect(canEditRoles("admin")).toBe(true);
    expect(canEditRoles("hiring_manager")).toBe(false);
    expect(canEditProfiles("recruiter")).toBe(true);
    expect(canEditProfiles("admin")).toBe(true);
    expect(canEditProfiles("hiring_manager")).toBe(false);
  });

  it("shows approval controls only to hiring managers", () => {
    expect(canApproveProfiles("hiring_manager")).toBe(true);
    expect(canApproveProfiles("recruiter")).toBe(false);
    expect(canApproveProfiles("admin")).toBe(false);
  });

  it("creates a neutral complete draft in canonical construct order", () => {
    const draft = blankConstructs();

    expect(draft.map(({ key }) => key)).toEqual(CONSTRUCT_KEYS);
    expect(draft.every(({ rating }) => rating === 3)).toBe(true);
  });

  it("sorts version history without mutating the API response", () => {
    const response = [profile(2), profile(1)];

    expect(sortProfiles(response).map(({ version }) => version)).toEqual([
      1, 2,
    ]);
    expect(response.map(({ version }) => version)).toEqual([2, 1]);
  });

  it("formats timestamps deterministically", () => {
    expect(formatDate("2026-09-26T23:30:00-04:00")).toBe("Sep 27, 2026");
  });
});
