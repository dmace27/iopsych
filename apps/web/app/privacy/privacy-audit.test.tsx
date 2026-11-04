// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  getCurrentUser: vi.fn(),
  getPrivacyStatus: vi.fn(),
  getPrivacyAssessments: vi.fn(),
  getPrivacyAuditEvents: vi.fn(),
}));
vi.mock("../../lib/api-client", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../lib/api-client")>()),
  ...api,
}));

import { PrivacyWorkspace } from "./privacy-workspace";

const assessmentId = "11111111-1111-4111-8111-111111111111";
const invitationId = "22222222-2222-4222-8222-222222222222";
const otherId = "33333333-3333-4333-8333-333333333333";
const relatedEvents = ["invitation", "consent", "report"].map(
  (entity, index) => ({
    id: `00000000-0000-4000-8000-${String(index).padStart(12, "0")}`,
    actor_id: null,
    entity_id: invitationId,
    entity_type: entity,
    event_type: `${entity}.created`,
    details: {},
    occurred_at: "2026-11-04T12:00:00Z",
  }),
);

describe("assessment-related audit history", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    api.getCurrentUser.mockResolvedValue({ role: "admin" });
    api.getPrivacyStatus.mockResolvedValue({
      active_assessments: 1,
      anonymized_assessments: 0,
      due_assessments: 0,
      next_retention_at: null,
      retention_days: 30,
      total_assessments: 1,
    });
    api.getPrivacyAuditEvents.mockResolvedValue([]);
    api.getPrivacyAssessments.mockResolvedValue({
      schema_version: "1.0",
      items: [
        {
          assessment_id: assessmentId,
          created_at: "2026-11-04T12:00:00Z",
          submitted_at: null,
          retention_expires_at: null,
          anonymized_at: null,
        },
      ],
      next_cursor: null,
    });
  });
  afterEach(cleanup);

  it("loads related events using the discovered assessment, and labels the displayed scope after selection changes", async () => {
    const user = userEvent.setup();
    render(<PrivacyWorkspace />);
    expect(
      await screen.findByText(/Organization-wide audit history/),
    ).toBeVisible();
    await user.type(screen.getByLabelText("Reference ID"), invitationId);
    await user.click(screen.getByRole("button", { name: "Find assessments" }));
    await user.click(
      await screen.findByRole("button", {
        name: `Select assessment ${assessmentId}`,
      }),
    );
    api.getPrivacyAuditEvents.mockResolvedValueOnce(relatedEvents);
    await user.click(
      screen.getByRole("button", { name: "Look up audit history" }),
    );
    expect(
      await screen.findByText(
        `Related history for assessment ${assessmentId}, including linked invitation, consent, and report events.`,
      ),
    ).toBeVisible();
    expect(api.getPrivacyAuditEvents).toHaveBeenLastCalledWith({
      assessment_id: assessmentId,
    });
    for (const event of relatedEvents)
      expect(screen.getByText(event.event_type)).toBeVisible();
    await user.clear(screen.getByLabelText("Assessment ID"));
    await user.type(screen.getByLabelText("Assessment ID"), otherId);
    expect(
      screen.getByText(/Related history for assessment/),
    ).toHaveTextContent(assessmentId);
    expect(
      screen.getByText(/Related history for assessment/),
    ).not.toHaveTextContent(otherId);
  });

  it("retains the loaded assessment scope and cursor when pagination fails and is retried", async () => {
    const user = userEvent.setup();
    const page = Array.from({ length: 50 }, (_, index) => ({
      ...relatedEvents[0],
      id: `00000000-0000-4000-8000-${String(index).padStart(12, "0")}`,
    }));
    render(<PrivacyWorkspace />);
    await screen.findByRole("heading", { name: "Candidate privacy" });
    await user.type(screen.getByLabelText("Assessment ID"), assessmentId);
    api.getPrivacyAuditEvents.mockResolvedValueOnce(page);
    await user.click(
      screen.getByRole("button", { name: "Look up audit history" }),
    );
    await screen.findByRole("button", { name: "Load more audit history" });
    await user.clear(screen.getByLabelText("Assessment ID"));
    await user.type(screen.getByLabelText("Assessment ID"), otherId);
    api.getPrivacyAuditEvents.mockRejectedValueOnce(
      new Error("History unavailable"),
    );
    await user.click(
      screen.getByRole("button", { name: "Load more audit history" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "History unavailable",
    );
    expect(screen.getAllByText("invitation.created")).toHaveLength(50);
    api.getPrivacyAuditEvents.mockResolvedValueOnce([]);
    await user.click(
      screen.getByRole("button", { name: "Load more audit history" }),
    );
    await waitFor(() =>
      expect(
        screen.queryByRole("button", { name: "Load more audit history" }),
      ).not.toBeInTheDocument(),
    );
    expect(api.getPrivacyAuditEvents).toHaveBeenLastCalledWith(
      { assessment_id: assessmentId },
      page.at(-1)?.id,
      50,
    );
    expect(
      screen.getByText("Loaded 0 additional audit events."),
    ).toHaveAttribute("aria-live", "polite");
  });
});
