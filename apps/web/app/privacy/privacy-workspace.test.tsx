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
  getPrivacyAssessments: vi.fn(),
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
    api.getPrivacyAssessments.mockResolvedValue({
      schema_version: "1.0",
      items: [],
      next_cursor: null,
    });
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
    expect(api.getPrivacyAssessments).not.toHaveBeenCalled();
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

const discoveryItem = {
  assessment_id: ASSESSMENT_ID,
  created_at: "2026-11-04T12:00:00Z",
  submitted_at: null,
  retention_expires_at: null,
  anonymized_at: null,
};

describe("privacy assessment discovery", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    api.getCurrentUser.mockResolvedValue({ role: "admin" });
    api.getPrivacyStatus.mockResolvedValue(privacyStatus);
    api.getPrivacyAuditEvents.mockResolvedValue([]);
    api.getPrivacyAssessments.mockResolvedValue({
      schema_version: "1.0",
      items: [discoveryItem],
      next_cursor: null,
    });
    api.exportCandidateData.mockResolvedValue(candidateExport);
  });
  afterEach(cleanup);

  it("selects an invitation result for export and clears stale data and confirmation on reference changes", async () => {
    const user = userEvent.setup();
    const storage = vi.spyOn(Storage.prototype, "setItem");
    render(<PrivacyWorkspace />);
    await screen.findByRole("heading", { name: "Find an assessment" });
    expect(
      screen.getByRole("button", { name: "Find assessments" }),
    ).toBeDisabled();
    await user.type(screen.getByLabelText("Reference ID"), INVITATION_ID);
    await user.click(screen.getByRole("button", { name: "Find assessments" }));
    await user.click(
      await screen.findByRole("button", {
        name: `Select assessment ${ASSESSMENT_ID}`,
      }),
    );
    expect(api.getPrivacyAssessments).toHaveBeenCalledWith({
      invitation_id: INVITATION_ID,
      limit: 20,
    });
    expect(screen.getByLabelText("Assessment ID")).toHaveValue(ASSESSMENT_ID);
    await user.click(
      screen.getByRole("button", { name: "Create JSON export" }),
    );
    await screen.findByRole("link", { name: "Download JSON export" });
    expect(api.exportCandidateData).toHaveBeenCalledWith(ASSESSMENT_ID);
    await user.click(
      screen.getByRole("button", { name: "Prepare anonymization" }),
    );
    expect(screen.getByText(/this revokes candidate access/)).toHaveTextContent(
      ASSESSMENT_ID,
    );
    await user.click(
      screen.getByRole("button", { name: "Cancel anonymization" }),
    );
    expect(api.deleteCandidateData).not.toHaveBeenCalled();
    await user.click(
      screen.getByRole("button", { name: "Prepare anonymization" }),
    );
    await user.clear(screen.getByLabelText("Reference ID"));
    expect(
      screen.queryByRole("button", { name: "Confirm anonymization" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: "Download JSON export" }),
    ).not.toBeInTheDocument();
    expect(screen.getByLabelText("Assessment ID")).toHaveValue("");
    expect(storage).not.toHaveBeenCalled();
    storage.mockRestore();
  });

  it("replaces bounded pages, preserves the role filter and opaque cursor, and retries errors", async () => {
    const user = userEvent.setup();
    api.getPrivacyAssessments
      .mockResolvedValueOnce({
        schema_version: "1.0",
        items: [discoveryItem],
        next_cursor: "opaque+/=",
      })
      .mockRejectedValueOnce(
        new ApiClientError("Invalid privacy cursor.", {
          code: "invalid_privacy_cursor",
          status: 422,
        }),
      )
      .mockResolvedValueOnce({
        schema_version: "1.0",
        items: [],
        next_cursor: null,
      });
    render(<PrivacyWorkspace />);
    await screen.findByRole("heading", { name: "Find an assessment" });
    await user.selectOptions(
      screen.getByLabelText("Reference type"),
      "role_id",
    );
    await user.type(screen.getByLabelText("Reference ID"), USER_ID);
    await user.click(screen.getByRole("button", { name: "Find assessments" }));
    await user.click(
      await screen.findByRole("button", { name: "Next assessment page" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Invalid privacy cursor",
    );
    expect(api.getPrivacyAssessments).toHaveBeenLastCalledWith({
      role_id: USER_ID,
      limit: 20,
      cursor: "opaque+/=",
    });
    await user.click(
      screen.getByRole("button", { name: "Next assessment page" }),
    );
    expect(await screen.findByText(/No matching assessments/)).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "Next assessment page" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", {
        name: `Select assessment ${ASSESSMENT_ID}`,
      }),
    ).not.toBeInTheDocument();
  });

  it("shows loading, locks reference changes, and handles expired lookup sessions", async () => {
    const user = userEvent.setup();
    let rejectLookup!: (error: unknown) => void;
    api.getPrivacyAssessments.mockReturnValueOnce(
      new Promise((_, reject) => {
        rejectLookup = reject;
      }),
    );
    render(<PrivacyWorkspace />);
    await screen.findByRole("heading", { name: "Find an assessment" });
    await user.type(screen.getByLabelText("Reference ID"), INVITATION_ID);
    await user.click(screen.getByRole("button", { name: "Find assessments" }));
    expect(screen.getByRole("status")).toHaveTextContent("Finding assessments");
    expect(screen.getByLabelText("Reference ID")).toBeDisabled();
    expect(screen.getByLabelText("Reference type")).toBeDisabled();
    rejectLookup(
      new ApiClientError("expired", { code: "unauthorized", status: 401 }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent("Sign in again");
    expect(
      screen.getByRole("button", { name: "Find assessments" }),
    ).toBeEnabled();
  });
});

describe("privacy discovery after mutations", () => {
  const OTHER_ID = "66666666-6666-4666-8666-666666666666";
  const UNAFFECTED_ID = "77777777-7777-4777-8777-777777777777";
  const anonymizedAt = "2026-11-04T13:00:00Z";
  const page = {
    schema_version: "1.0",
    items: [ASSESSMENT_ID, OTHER_ID, UNAFFECTED_ID].map((id) => ({
      ...discoveryItem,
      assessment_id: id,
    })),
    next_cursor: null,
  };

  beforeEach(() => {
    vi.resetAllMocks();
    api.getCurrentUser.mockResolvedValue({ role: "admin" });
    api.getPrivacyStatus.mockResolvedValue(privacyStatus);
    api.getPrivacyAuditEvents.mockResolvedValue([]);
    api.getPrivacyAssessments.mockResolvedValue(page);
    api.exportCandidateData.mockResolvedValue(candidateExport);
    api.deleteCandidateData.mockResolvedValue({
      already_anonymized: false,
      anonymized_at: anonymizedAt,
      assessment_id: ASSESSMENT_ID,
      reports_deleted: 2,
    });
    api.runPrivacyRetention.mockResolvedValue({
      anonymized_assessment_ids: [ASSESSMENT_ID, OTHER_ID],
      completed_at: anonymizedAt,
    });
  });
  afterEach(cleanup);

  async function selectResult() {
    const user = userEvent.setup();
    render(<PrivacyWorkspace />);
    await screen.findByRole("heading", { name: "Find an assessment" });
    await user.type(screen.getByLabelText("Reference ID"), INVITATION_ID);
    await user.click(screen.getByRole("button", { name: "Find assessments" }));
    await user.click(
      await screen.findByRole("button", {
        name: `Select assessment ${ASSESSMENT_ID}`,
      }),
    );
    return user;
  }

  function card(id: string) {
    return screen
      .getByRole("button", {
        name: `Select assessment ${id}`,
      })
      .closest("li");
  }

  it("reconciles anonymization while preserving selection and clearing export and confirmation", async () => {
    const user = await selectResult();
    await user.click(
      screen.getByRole("button", { name: "Create JSON export" }),
    );
    await screen.findByRole("link", { name: "Download JSON export" });
    await user.click(
      screen.getByRole("button", { name: "Prepare anonymization" }),
    );
    await user.click(
      screen.getByRole("button", { name: "Confirm anonymization" }),
    );

    expect(await screen.findByText(/Derived reports removed: 2/)).toBeVisible();
    expect(card(ASSESSMENT_ID)).toHaveTextContent(
      `Anonymized: ${anonymizedAt}`,
    );
    expect(card(OTHER_ID)).toHaveTextContent("Anonymized: No");
    expect(screen.getByLabelText("Assessment ID")).toHaveValue(ASSESSMENT_ID);
    expect(
      screen.queryByRole("link", { name: "Download JSON export" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Confirm anonymization" }),
    ).not.toBeInTheDocument();
    expect(api.getPrivacyAssessments).toHaveBeenCalledOnce();
  });

  it("reconciles every retention result and clears affected selection artifacts", async () => {
    const user = await selectResult();
    await user.click(
      screen.getByRole("button", { name: "Create JSON export" }),
    );
    await screen.findByRole("link", { name: "Download JSON export" });
    await user.click(
      screen.getByRole("button", { name: "Prepare anonymization" }),
    );
    await user.click(screen.getByRole("button", { name: "Run retention now" }));

    expect(
      await screen.findByText("Retention run anonymized 2 assessments."),
    ).toBeInTheDocument();
    expect(card(ASSESSMENT_ID)).toHaveTextContent("Anonymized: Yes");
    expect(card(OTHER_ID)).toHaveTextContent("Anonymized: Yes");
    expect(card(UNAFFECTED_ID)).toHaveTextContent("Anonymized: No");
    expect(screen.getByLabelText("Assessment ID")).toHaveValue(ASSESSMENT_ID);
    expect(
      screen.queryByRole("link", { name: "Download JSON export" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Confirm anonymization" }),
    ).not.toBeInTheDocument();
  });

  it("preserves unaffected selection artifacts when retention changes another row", async () => {
    api.runPrivacyRetention.mockResolvedValue({
      anonymized_assessment_ids: [OTHER_ID],
      completed_at: anonymizedAt,
    });
    const user = await selectResult();
    await user.click(
      screen.getByRole("button", { name: "Create JSON export" }),
    );
    await screen.findByRole("link", { name: "Download JSON export" });
    await user.click(
      screen.getByRole("button", { name: "Prepare anonymization" }),
    );
    await user.click(screen.getByRole("button", { name: "Run retention now" }));

    await screen.findByText("Retention run anonymized 1 assessments.");
    expect(card(OTHER_ID)).toHaveTextContent("Anonymized: Yes");
    expect(card(ASSESSMENT_ID)).toHaveTextContent("Anonymized: No");
    expect(
      screen.getByRole("link", { name: "Download JSON export" }),
    ).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Confirm anonymization" }),
    ).toBeVisible();
  });

  it.each(["anonymization", "retention"])(
    "does not report success or change lifecycle data after failed %s",
    async (operation) => {
      const user = await selectResult();
      api.deleteCandidateData.mockRejectedValue(new Error("Mutation failed"));
      api.runPrivacyRetention.mockRejectedValue(new Error("Mutation failed"));
      if (operation === "anonymization") {
        await user.click(
          screen.getByRole("button", { name: "Prepare anonymization" }),
        );
        await user.click(
          screen.getByRole("button", { name: "Confirm anonymization" }),
        );
      } else {
        await user.click(
          screen.getByRole("button", { name: "Run retention now" }),
        );
      }

      expect(await screen.findByRole("alert")).toHaveTextContent(
        "Mutation failed",
      );
      expect(card(ASSESSMENT_ID)).toHaveTextContent("Anonymized: No");
      expect(card(OTHER_ID)).toHaveTextContent("Anonymized: No");
      expect(
        screen.queryByText(/was anonymized|Retention run anonymized/),
      ).not.toBeInTheDocument();
      expect(api.getPrivacyStatus).toHaveBeenCalledOnce();
    },
  );

  it.each(["anonymization", "retention"])(
    "keeps truthful %s success when status refresh fails",
    async (operation) => {
      const user = await selectResult();
      api.getPrivacyStatus.mockRejectedValueOnce(
        new Error("Status unavailable"),
      );
      if (operation === "anonymization") {
        await user.click(
          screen.getByRole("button", { name: "Prepare anonymization" }),
        );
        await user.click(
          screen.getByRole("button", { name: "Confirm anonymization" }),
        );
      } else {
        await user.click(
          screen.getByRole("button", { name: "Run retention now" }),
        );
      }

      expect(await screen.findByRole("alert")).toHaveTextContent(
        "The operation completed, but privacy status and audit history could not be refreshed.",
      );
      expect(card(ASSESSMENT_ID)).not.toHaveTextContent("Anonymized: No");
      expect(
        screen.getByText(
          operation === "anonymization"
            ? /Derived reports removed: 2/
            : "Retention run anonymized 2 assessments.",
        ),
      ).toBeInTheDocument();
    },
  );

  it("locks discovery through a pending mutation and delayed status refresh", async () => {
    const user = await selectResult();
    let resolveRetention!: (value: {
      anonymized_assessment_ids: string[];
      completed_at: string;
    }) => void;
    let resolveStatus!: (value: PrivacyStatus) => void;
    api.runPrivacyRetention.mockReturnValueOnce(
      new Promise((resolve) => {
        resolveRetention = resolve;
      }),
    );
    api.getPrivacyStatus.mockReturnValueOnce(
      new Promise((resolve) => {
        resolveStatus = resolve;
      }),
    );
    await user.click(
      screen.getByRole("button", { name: "Prepare anonymization" }),
    );
    await user.click(screen.getByRole("button", { name: "Run retention now" }));
    expect(
      screen.getByRole("button", { name: "Find assessments" }),
    ).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Confirm anonymization" }),
    ).toBeDisabled();
    expect(card(ASSESSMENT_ID)).toHaveTextContent("Anonymized: No");
    resolveRetention({
      anonymized_assessment_ids: [ASSESSMENT_ID, OTHER_ID],
      completed_at: anonymizedAt,
    });
    await screen.findByText("Retention run anonymized 2 assessments.");
    expect(card(ASSESSMENT_ID)).toHaveTextContent("Anonymized: Yes");
    expect(card(OTHER_ID)).toHaveTextContent("Anonymized: Yes");
    expect(
      screen.getByRole("button", { name: "Find assessments" }),
    ).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Find assessments" }));
    expect(api.getPrivacyAssessments).toHaveBeenCalledOnce();
    await waitFor(() => expect(api.getPrivacyStatus).toHaveBeenCalledTimes(2));
    resolveStatus(privacyStatus);
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Find assessments" }),
      ).toBeEnabled(),
    );
    expect(
      screen.getByText("Retention run anonymized 2 assessments."),
    ).toBeInTheDocument();
    expect(card(ASSESSMENT_ID)).toHaveTextContent("Anonymized: Yes");
  });

  it.each(["anonymization", "retention"])(
    "prevents delayed stale lookup data from reverting confirmed %s",
    async (operation) => {
      const user = await selectResult();
      if (operation === "anonymization") {
        await user.click(
          screen.getByRole("button", { name: "Prepare anonymization" }),
        );
        await user.click(
          screen.getByRole("button", { name: "Confirm anonymization" }),
        );
      } else {
        await user.click(
          screen.getByRole("button", { name: "Run retention now" }),
        );
      }
      await waitFor(() =>
        expect(
          screen.getByRole("button", { name: "Find assessments" }),
        ).toBeEnabled(),
      );
      let resolveLookup!: (value: typeof page) => void;
      api.getPrivacyAssessments.mockReturnValueOnce(
        new Promise((resolve) => {
          resolveLookup = resolve;
        }),
      );
      await user.click(
        screen.getByRole("button", { name: "Find assessments" }),
      );
      expect(
        screen.getByRole("button", { name: "Run retention now" }),
      ).toBeDisabled();
      expect(screen.getByLabelText("Reference ID")).toBeDisabled();
      resolveLookup(page);
      await screen.findByRole("button", {
        name: `Select assessment ${ASSESSMENT_ID}`,
      });
      expect(card(ASSESSMENT_ID)).not.toHaveTextContent("Anonymized: No");
      expect(card(OTHER_ID)).toHaveTextContent(
        operation === "retention" ? "Anonymized: Yes" : "Anonymized: No",
      );
    },
  );
});
