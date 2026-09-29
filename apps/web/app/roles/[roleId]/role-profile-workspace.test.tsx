/** @vitest-environment jsdom */

import { CONSTRUCT_KEYS } from "@iopsych/shared";
import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const apiMocks = vi.hoisted(() => ({
  approveRoleProfile: vi.fn(),
  createRoleProfile: vi.fn(),
  extractRoleProfile: vi.fn(),
  getCurrentUser: vi.fn(),
  getRole: vi.fn(),
  getRoleProfiles: vi.fn(),
  reviseRoleProfile: vi.fn(),
}));

vi.mock("../../../lib/api-client", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../../lib/api-client")>()),
  ...apiMocks,
}));

import type { CurrentUser, Role, RoleProfile } from "../../../lib/contracts";
import { RoleProfileWorkspace } from "./role-profile-workspace";

const IDS = {
  manager: "11111111-1111-4111-8111-111111111111",
  organization: "22222222-2222-4222-8222-222222222222",
  profile: "33333333-3333-4333-8333-333333333333",
  profile2: "44444444-4444-4444-8444-444444444444",
  role: "55555555-5555-4555-8555-555555555555",
} as const;

/** Return the complete role reviewed by this focused interaction test. */
function role(status: Role["status"] = "draft"): Role {
  return {
    created_at: "2026-09-26T12:00:00Z",
    department: "Engineering",
    id: IDS.role,
    job_description: "Own service reliability and incident response.",
    location: "Toronto",
    organization_id: IDS.organization,
    status,
    title: "Platform Engineer",
  };
}

/** Return a complete, evidence-backed profile snapshot for every construct. */
function profile(
  version = 1,
  status: RoleProfile["status"] = "draft",
): RoleProfile {
  return {
    approved_at: status === "approved" ? "2026-09-26T13:00:00Z" : null,
    approved_by: status === "approved" ? IDS.manager : null,
    assumptions: [],
    constructs: CONSTRUCT_KEYS.map((key) => ({
      confidence: "high" as const,
      evidence: ["Own service reliability and incident response."],
      key,
      rationale: "The source description supports this rating.",
      rating: 4 as const,
    })),
    created_at: "2026-09-26T12:00:00Z",
    created_by: IDS.manager,
    id: version === 1 ? IDS.profile : IDS.profile2,
    role_id: IDS.role,
    status,
    version,
  };
}

/** Return the hiring-manager identity required by the approval gate. */
function manager(): CurrentUser {
  return {
    email: "manager@example.invalid",
    id: IDS.manager,
    name: "Hiring Manager",
    organization_id: IDS.organization,
    role: "hiring_manager",
  };
}

describe("RoleProfileWorkspace", () => {
  beforeEach(() => {
    Object.values(apiMocks).forEach((mock) => mock.mockReset());
    apiMocks.getCurrentUser.mockResolvedValue(manager());
    vi.stubGlobal("scrollTo", vi.fn());
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("lets a hiring manager revise the latest draft without overwriting history", async () => {
    const original = profile();
    const revision = profile(2);
    apiMocks.getRole.mockResolvedValue(role());
    apiMocks.getRoleProfiles.mockResolvedValue([original]);
    apiMocks.reviseRoleProfile.mockResolvedValue(revision);
    const user = userEvent.setup();
    render(<RoleProfileWorkspace roleId={IDS.role} />);

    const saveButton = await screen.findByRole("button", {
      name: "Save new version",
    });
    await user.click(saveButton);

    await waitFor(() => {
      expect(apiMocks.reviseRoleProfile).toHaveBeenCalledWith(
        IDS.role,
        IDS.profile,
        expect.objectContaining({
          constructs: expect.arrayContaining([
            expect.objectContaining({ key: "autonomy", rating: 4 }),
          ]),
        }),
      );
    });
    expect(await screen.findByText("Profile version 2")).toBeInTheDocument();
    expect(screen.getByText("Version 1")).toBeInTheDocument();
    expect(screen.getByText("Version 2")).toBeInTheDocument();
  });

  it("lets a recruiter extract a draft while keeping manager approval separate", async () => {
    const extracted = {
      ...profile(),
      assumptions: ["The description may not cover every team routine."],
    };
    apiMocks.getCurrentUser.mockResolvedValue({
      ...manager(),
      role: "recruiter",
    });
    apiMocks.getRole.mockResolvedValue(role());
    apiMocks.getRoleProfiles.mockResolvedValue([]);
    apiMocks.extractRoleProfile.mockResolvedValue(extracted);
    const user = userEvent.setup();
    render(<RoleProfileWorkspace roleId={IDS.role} />);

    await user.click(
      await screen.findByRole("button", {
        name: "Extract profile from job description",
      }),
    );

    await waitFor(() => {
      expect(apiMocks.extractRoleProfile).toHaveBeenCalledWith(IDS.role);
    });
    expect(
      await screen.findByText("Extraction assumptions to verify"),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /approve version/i }),
    ).not.toBeInTheDocument();
  });

  it("exposes approval only to the manager and refreshes the frozen version", async () => {
    const draft = profile();
    const approved = profile(1, "approved");
    apiMocks.getRole
      .mockResolvedValueOnce(role())
      .mockResolvedValueOnce(role("active"));
    apiMocks.getRoleProfiles
      .mockResolvedValueOnce([draft])
      .mockResolvedValueOnce([approved]);
    apiMocks.approveRoleProfile.mockResolvedValue(approved);
    const user = userEvent.setup();
    render(<RoleProfileWorkspace roleId={IDS.role} />);

    await user.click(
      await screen.findByRole("button", { name: "Approve version 1" }),
    );

    await waitFor(() => {
      expect(apiMocks.approveRoleProfile).toHaveBeenCalledWith(
        IDS.role,
        IDS.profile,
      );
    });
    expect(
      await screen.findByText(/approved versions are frozen/i),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Approve version 1" }),
    ).not.toBeInTheDocument();
  });
});
