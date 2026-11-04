// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CandidateDataExportSchema } from "./privacy-contracts";
import { exportCandidateData } from "./api-client";
import { PrivacyWorkspace } from "../app/privacy/privacy-workspace";

vi.mock("./api-client", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./api-client")>()),
  getCurrentUser: vi.fn().mockResolvedValue({ role: "admin" }),
  getPrivacyStatus: vi.fn().mockResolvedValue({ retention_days: 90 }),
  getPrivacyAuditEvents: vi.fn().mockResolvedValue([]),
}));

const id = "11111111-1111-4111-8111-111111111111";
const timestamp = "2026-11-04T12:00:00Z";
const snapshot = {
  schema_version: 1,
  retention_days: 37,
  consent_notice: {
    version: "synthetic-v1",
    purpose: "Work preferences.",
    data_use: "Interview preparation.",
    retention: "37 days.",
    accommodation_contact_email: "access@example.invalid",
    privacy_contact_email: "privacy@example.invalid",
    decline_without_penalty: true,
  },
};
const metadata = {
  notice_snapshot: snapshot,
  notice_sha256: "a".repeat(64),
  notice_snapshot_origin: "first_presented",
  notice_snapshot_recorded_at: timestamp,
  presented_notice_sha256: "a".repeat(64),
  notice_history: "digest_recorded",
};
const legacy = {
  schema_version: "1.0",
  generated_at: timestamp,
  organization: {
    name: "Synthetic",
    role_title: "Engineer",
    role_profile_version: 1,
  },
  invitation: {
    id,
    email: "candidate@example.invalid",
    status: "consented",
    created_at: timestamp,
    sent_at: timestamp,
    expires_at: timestamp,
    revoked_at: null,
  },
  consent: {
    id,
    decision: "consent",
    notice_version: "synthetic-v1",
    recorded_at: timestamp,
  },
  assessment: {
    id,
    created_at: timestamp,
    submitted_at: timestamp,
    retention_expires_at: timestamp,
    definition: {},
    responses: {},
    scores: {},
  },
  reports: [],
  activity: [],
};
const withConsent = (fields: Record<string, unknown>) => ({
  ...legacy,
  consent: { ...legacy.consent, ...fields },
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("notice export rolling compatibility", () => {
  it.each([
    legacy,
    withConsent(metadata),
    withConsent(
      Object.fromEntries(Object.keys(metadata).map((key) => [key, null])),
    ),
    withConsent({ notice_history: "legacy_unknown" }),
  ])(
    "preserves legacy and additive exports through the actual client and download",
    async (payload) => {
      vi.stubGlobal(
        "fetch",
        vi.fn().mockImplementation(async () => Response.json(payload)),
      );
      expect(CandidateDataExportSchema.parse(payload)).toEqual(payload);
      await expect(exportCandidateData(id)).resolves.toEqual(payload);
      const user = userEvent.setup();
      render(<PrivacyWorkspace />);
      await screen.findByText("Policy window: 90 days");
      await user.type(screen.getByLabelText("Assessment ID"), id);
      await user.click(
        screen.getByRole("button", { name: "Create JSON export" }),
      );
      const link = await screen.findByRole("link", {
        name: "Download JSON export",
      });
      expect(link).toHaveAttribute("download", `candidate-data-${id}.json`);
      expect(
        JSON.parse(
          decodeURIComponent(link.getAttribute("href")!.split(",")[1]!),
        ),
      ).toEqual(payload);
      expect(fetch).toHaveBeenLastCalledWith(
        `/api/internal/candidates/${id}/export`,
        expect.objectContaining({ cache: "no-store" }),
      );
    },
  );

  it.each(["issued", "first_presented", "legacy_decision"])(
    "accepts origin %s",
    (notice_snapshot_origin) => {
      expect(
        CandidateDataExportSchema.safeParse(
          withConsent({ ...metadata, notice_snapshot_origin }),
        ).success,
      ).toBe(true);
    },
  );

  it.each([
    "not_recorded",
    "digest_recorded",
    "legacy_unverified",
    "legacy_unknown",
  ])("accepts history %s", (notice_history) => {
    expect(
      CandidateDataExportSchema.safeParse(
        withConsent({ ...metadata, notice_history }),
      ).success,
    ).toBe(true);
  });

  it.each([
    { notice_sha256: "A".repeat(64) },
    { presented_notice_sha256: "g".repeat(64) },
    { notice_sha256: "a".repeat(63) },
    { notice_history: "verified_read" },
    { notice_snapshot_origin: "backfilled" },
    { notice_snapshot_recorded_at: "yesterday" },
    { notice_snapshot: {} },
    { notice_snapshot: { ...snapshot, schema_version: "1" } },
    ...[0, 3651, 1.5, "37", true].map((retention_days) => ({
      notice_snapshot: { ...snapshot, retention_days },
    })),
    { notice_snapshot: { ...snapshot, extra: true } },
    ...[
      { extra: true },
      { purpose: " " },
      { purpose: "\ud800" },
      { version: "x".repeat(81) },
      { decline_without_penalty: "true" },
    ].map((notice) => ({
      notice_snapshot: {
        ...snapshot,
        consent_notice: { ...snapshot.consent_notice, ...notice },
      },
    })),
    { unexpected: true },
  ])("rejects malformed or unknown consent additions %j", async (fields) => {
    const payload = withConsent({ ...metadata, ...fields });
    expect(CandidateDataExportSchema.safeParse(payload).success).toBe(false);
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json(payload)));
    await expect(exportCandidateData(id)).rejects.toMatchObject({
      code: "invalid_api_response",
    });
  });

  it("keeps existing export objects strict", () => {
    for (const field of ["organization", "invitation", "assessment"] as const) {
      expect(
        CandidateDataExportSchema.safeParse({
          ...legacy,
          [field]: { ...legacy[field], unexpected: true },
        }).success,
      ).toBe(false);
    }
    expect(
      CandidateDataExportSchema.safeParse({ ...legacy, unexpected: true })
        .success,
    ).toBe(false);
  });
});
