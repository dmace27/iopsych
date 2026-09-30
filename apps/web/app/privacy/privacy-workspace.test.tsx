// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type {
  CandidateDataExport,
  PrivacyAuditEvent,
  PrivacyStatus,
} from "../../lib/privacy-contracts";

const api = vi.hoisted(() => ({
  deleteCandidateData: vi.fn(),
  exportCandidateData: vi.fn(),
  getCurrentUser: vi.fn(),
  getPrivacyAuditEvents: vi.fn(),
  getPrivacyStatus: vi.fn(),
  runPrivacyRetention: vi.fn(),
}));
vi.mock("../../lib/api-client", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../lib/api-client")>()),
  ...api,
}));

import { ApiClientError } from "../../lib/api-client";
import { PrivacyWorkspace } from "./privacy-workspace";

const ASSESSMENT_ID = "11111111-1111-4111-8111-111111111111";
const USER_ID = "22222222-2222-4222-8222-222222222222";
const INVITATION_ID = "33333333-3333-4333-8333-333333333333";
const CONSENT_ID = "44444444-4444-4444-8444-444444444444";

const privacyStatus: PrivacyStatus = {
  active_assessments: 2,
  anonymized_assessments: 1,
  due_assessments: 1,
  next_retention_at: "2026-10-01T12:00:00Z",
  retention_days: 30,
  total_assessments: 3,
};

const auditEvent: PrivacyAuditEvent = {
  actor_id: USER_ID,
  details: { outcome: "succeeded" },
  entity_id: ASSESSMENT_ID,
  entity_type: "assessment",
  event_type: "candidate_data.exported",
  id: "55555555-5555-4555-8555-555555555555",
  occurred_at: "2026-09-29T12:00:00Z",
};

const candidateExport: CandidateDataExport = {
  activity: [],
  assessment: {
    created_at: "2026-09-01T11:59:00Z",
    definition: {},
    id: ASSESSMENT_ID,
    responses: {},
    retention_expires_at: "2026-10-01T12:00:00Z",
    scores: {},
    submitted_at: "2026-09-01T12:00:00Z",
  },
  consent: {
    decision: "consent",
    id: CONSENT_ID,
    notice_version: "pilot-v1",
    recorded_at: "2026-09-01T11:00:00Z",
  },
  generated_at: "2026-09-29T12:00:00Z",
  invitation: {
    created_at: "2026-08-31T12:00:00Z",
    email: "candidate@example.test",
    expires_at: "2026-10-01T12:00:00Z",
    id: INVITATION_ID,
    revoked_at: null,
    sent_at: "2026-08-31T12:01:00Z",
    status: "consented",
  },
  organization: {
    name: "Alpha Labs",
    role_profile_version: 1,
    role_title: "Engineer",
  },
  reports: [],
  schema_version: "1.0",
};

describe("PrivacyWorkspace", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    api.getCurrentUser.mockResolvedValue({ role: "admin" });
    api.getPrivacyStatus.mockResolvedValue(privacyStatus);
    api.getPrivacyAuditEvents.mockResolvedValue([auditEvent]);
    api.exportCandidateData.mockResolvedValue(candidateExport);
    api.deleteCandidateData.mockResolvedValue({
      already_anonymized: false,
      anonymized_at: "2026-09-29T12:01:00Z",
      assessment_id: ASSESSMENT_ID,
      reports_deleted: 2,
    });
    api.runPrivacyRetention.mockResolvedValue({
      anonymized_assessment_ids: [ASSESSMENT_ID],
      completed_at: "2026-09-29T12:02:00Z",
    });
  });

  afterEach(cleanup);

  it("denies non-admin users before reading privacy data", async () => {
    api.getCurrentUser.mockResolvedValue({ role: "recruiter" });

    render(<PrivacyWorkspace />);

    expect(
      await screen.findByRole("heading", {
        name: "Administrator access required",
      }),
    ).toBeVisible();
    expect(api.getPrivacyStatus).not.toHaveBeenCalled();
    expect(api.getPrivacyAuditEvents).not.toHaveBeenCalled();
  });

  it("exports and explicitly confirms irreversible anonymization", async () => {
    const user = userEvent.setup();
    render(<PrivacyWorkspace />);

    expect(await screen.findByText("Policy window: 30 days")).toBeVisible();
    expect(screen.getByText(/Next deadline:/)).toHaveTextContent("2026-10-01");
    expect(screen.getByText("candidate_data.exported")).toBeVisible();
    expect(screen.getByText(/"outcome": "succeeded"/)).toBeVisible();
    const input = screen.getByLabelText("Assessment ID");
    await user.type(input, ASSESSMENT_ID);
    await user.click(
      screen.getByRole("button", { name: "Create JSON export" }),
    );

    const download = await screen.findByRole("link", {
      name: "Download JSON export",
    });
    expect(api.exportCandidateData).toHaveBeenCalledWith(ASSESSMENT_ID);
    expect(download).toHaveAttribute(
      "download",
      `candidate-data-${ASSESSMENT_ID}.json`,
    );
    expect(download.getAttribute("href")).toContain("data:application/json");

    await user.click(
      screen.getByRole("button", { name: "Prepare anonymization" }),
    );
    expect(api.deleteCandidateData).not.toHaveBeenCalled();
    await user.click(
      screen.getByRole("button", { name: "Confirm anonymization" }),
    );

    expect(await screen.findByText(/Derived reports removed: 2/)).toBeVisible();
    expect(api.deleteCandidateData).toHaveBeenCalledWith(ASSESSMENT_ID);
    expect(api.getPrivacyAuditEvents).toHaveBeenLastCalledWith(ASSESSMENT_ID);
    expect(
      screen.queryByRole("link", { name: "Download JSON export" }),
    ).not.toBeInTheDocument();
  });

  it("runs retention, filters audit history, and reports action failures", async () => {
    const user = userEvent.setup();
    api.exportCandidateData.mockRejectedValueOnce(
      new ApiClientError("Candidate data has already been anonymized.", {
        code: "candidate_data_anonymized",
        status: 410,
      }),
    );
    render(<PrivacyWorkspace />);
    await screen.findByRole("heading", { name: "Candidate privacy" });

    await user.click(screen.getByRole("button", { name: "Run retention now" }));
    await waitFor(() => expect(api.runPrivacyRetention).toHaveBeenCalledOnce());
    expect(api.getPrivacyStatus).toHaveBeenCalledTimes(2);

    await user.type(screen.getByLabelText("Assessment ID"), ASSESSMENT_ID);
    await user.click(
      screen.getByRole("button", { name: "Look up audit history" }),
    );
    await waitFor(() =>
      expect(api.getPrivacyAuditEvents).toHaveBeenLastCalledWith(ASSESSMENT_ID),
    );
    await user.click(
      screen.getByRole("button", { name: "Create JSON export" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Candidate data has already been anonymized.",
    );
  });

  it("shows an expired-session error and retries the initial load", async () => {
    const user = userEvent.setup();
    api.getCurrentUser.mockRejectedValueOnce(
      new ApiClientError("expired", { code: "unauthorized", status: 401 }),
    );
    render(<PrivacyWorkspace />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Your internal session is missing or expired",
    );
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(
      await screen.findByRole("heading", { name: "Candidate privacy" }),
    ).toBeVisible();
  });

  it("paginates audit history without dropping the active entity filter", async () => {
    const user = userEvent.setup();
    const firstPage = Array.from({ length: 50 }, (_, index) => ({
      ...auditEvent,
      id: `00000000-0000-4000-8000-${String(index).padStart(12, "0")}`,
    }));
    const secondPage = [
      {
        ...auditEvent,
        event_type: "candidate_data.anonymized",
        id: "99999999-9999-4999-8999-999999999999",
      },
    ];
    api.getPrivacyAuditEvents
      .mockResolvedValueOnce(firstPage)
      .mockResolvedValueOnce(firstPage)
      .mockResolvedValueOnce(secondPage);
    render(<PrivacyWorkspace />);
    await screen.findByRole("heading", { name: "Candidate privacy" });
    await user.type(screen.getByLabelText("Assessment ID"), ASSESSMENT_ID);
    await user.click(
      screen.getByRole("button", { name: "Look up audit history" }),
    );
    await screen.findByRole("button", { name: "Load more audit history" });
    await user.click(
      screen.getByRole("button", { name: "Load more audit history" }),
    );

    expect(await screen.findByText("candidate_data.anonymized")).toBeVisible();
    expect(api.getPrivacyAuditEvents).toHaveBeenLastCalledWith(
      ASSESSMENT_ID,
      firstPage.at(-1)?.id,
      50,
    );
    expect(
      screen.queryByRole("button", { name: "Load more audit history" }),
    ).not.toBeInTheDocument();
  });
});
