// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { act, cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  getCurrentUser: vi.fn(),
  getPrivacyStatus: vi.fn(),
  getPrivacyAuditEvents: vi.fn(),
  runPrivacyRetention: vi.fn(),
}));
vi.mock("../../lib/api-client", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../lib/api-client")>()),
  ...api,
}));

import { PrivacyWorkspace } from "./privacy-workspace";

const assessmentId = "11111111-1111-4111-8111-111111111111";
const otherId = "33333333-3333-4333-8333-333333333333";
const page = Array.from({ length: 50 }, (_, index) => ({
  id: `00000000-0000-4000-8000-${String(index).padStart(12, "0")}`,
  actor_id: null,
  entity_id: assessmentId,
  entity_type: "assessment",
  event_type: "assessment.submitted",
  details: {},
  occurred_at: "2026-11-04T12:00:00Z",
}));

function deferredPage() {
  let resolve!: (value: typeof page) => void;
  let reject!: (error: Error) => void;
  const promise = new Promise<typeof page>((yes, no) => {
    resolve = yes;
    reject = no;
  });
  return { promise, resolve, reject };
}

describe("obsolete privacy audit callbacks", () => {
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
    api.getPrivacyAuditEvents.mockResolvedValue(page);
    api.runPrivacyRetention.mockResolvedValue({
      anonymized_assessment_ids: [assessmentId],
    });
  });
  afterEach(cleanup);

  it.each(["resolve", "reject"] as const)(
    "ignores obsolete %s feedback and does not unlock a newer pagination request",
    async (outcome) => {
      const user = userEvent.setup();
      const old = deferredPage();
      const current = deferredPage();
      render(<PrivacyWorkspace />);
      await screen.findByRole("button", { name: "Load more audit history" });
      api.getPrivacyAuditEvents.mockReturnValueOnce(old.promise);
      await user.click(
        screen.getByRole("button", { name: "Load more audit history" }),
      );
      await user.type(screen.getByLabelText("Assessment ID"), otherId);
      await user.click(
        screen.getByRole("button", { name: "Look up audit history" }),
      );
      await screen.findByText(
        `Related history for assessment ${otherId}, including linked invitation, consent, and report events.`,
      );
      api.getPrivacyAuditEvents.mockReturnValueOnce(current.promise);
      await user.click(
        screen.getByRole("button", { name: "Load more audit history" }),
      );
      await act(async () => {
        if (outcome === "resolve") old.resolve(page);
        else old.reject(new Error("Obsolete page failed"));
      });
      expect(screen.queryByRole("alert")).not.toBeInTheDocument();
      expect(
        screen.queryByText(/Loaded 50 additional/),
      ).not.toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: "Loading audit history…" }),
      ).toBeDisabled();
      expect(screen.getAllByText("assessment.submitted")).toHaveLength(50);
      await act(async () => current.resolve([]));
      expect(
        screen.getByText("Loaded 0 additional audit events."),
      ).toBeInTheDocument();
    },
  );

  it.each(["resolve", "reject"] as const)(
    "preserves retention success and refresh error after obsolete pagination %s",
    async (outcome) => {
      const user = userEvent.setup();
      const old = deferredPage();
      render(<PrivacyWorkspace />);
      await screen.findByRole("button", { name: "Load more audit history" });
      api.getPrivacyAuditEvents.mockReturnValueOnce(old.promise);
      await user.click(
        screen.getByRole("button", { name: "Load more audit history" }),
      );
      api.getPrivacyStatus.mockRejectedValueOnce(new Error("Refresh failed"));
      await user.click(
        screen.getByRole("button", { name: "Run retention now" }),
      );
      expect(await screen.findByRole("alert")).toHaveTextContent(
        "The operation completed",
      );
      await act(async () => {
        if (outcome === "resolve") old.resolve(page);
        else old.reject(new Error("Obsolete page failed"));
      });
      expect(screen.getByRole("alert")).toHaveTextContent("Refresh failed");
      expect(screen.getByRole("alert")).not.toHaveTextContent(
        "Obsolete page failed",
      );
      expect(
        screen.getByText("Retention run anonymized 1 assessments."),
      ).toBeInTheDocument();
      expect(screen.getAllByText("assessment.submitted")).toHaveLength(50);
    },
  );
});
