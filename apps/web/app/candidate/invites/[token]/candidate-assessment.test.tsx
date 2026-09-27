/** @vitest-environment jsdom */

import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const apiMocks = vi.hoisted(() => ({
  getCandidateInvite: vi.fn(),
  recordCandidateConsent: vi.fn(),
}));

vi.mock("../../../../lib/candidate-api", () => apiMocks);

import type { CandidateInvite } from "../../../../lib/candidate-contracts";
import { CandidateAssessment } from "./candidate-assessment";

const INVITATION_ID = "11111111-1111-4111-8111-111111111111";

function candidateInvite(
  overrides: Partial<CandidateInvite> = {},
): CandidateInvite {
  return {
    can_start_assessment: false,
    consent_notice: {
      accommodation_contact_email: "access@pilot.example",
      data_use:
        "Responses are used to prepare human-reviewed interview questions.",
      decline_without_penalty: true,
      privacy_contact_email: "privacy@pilot.example",
      purpose: "Understand work preferences for the Platform Engineer role.",
      retention: "Pilot data is kept for 90 days.",
      version: "pilot-1",
    },
    decision: null,
    decision_recorded_at: null,
    expires_at: "2026-10-01T16:00:00Z",
    invitation_id: INVITATION_ID,
    organization_name: "Northstar Labs",
    role_title: "Platform Engineer",
    status: "active",
    ...overrides,
  };
}

describe("CandidateAssessment", () => {
  beforeEach(() => {
    apiMocks.getCandidateInvite.mockReset();
    apiMocks.recordCandidateConsent.mockReset();
    window.localStorage.clear();
  });

  afterEach(cleanup);

  it("does not expose any assessment question before affirmative consent", async () => {
    apiMocks.getCandidateInvite.mockResolvedValue(candidateInvite());
    render(<CandidateAssessment token="signed-token" />);

    expect(
      await screen.findByRole("heading", {
        name: "Your choice and your data",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/assessment questions remain hidden/i),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(/I prefer to decide how I organize my workday/i),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("link", {
        name: /request a copy, correction, or deletion/i,
      }),
    ).toHaveAttribute("href", expect.stringContaining("privacy@pilot.example"));
  });

  it("records a keyboard consent choice and completes all blocks by keyboard", async () => {
    const consented = candidateInvite({
      can_start_assessment: true,
      decision: "consent",
      decision_recorded_at: "2026-09-27T12:00:00Z",
      status: "consented",
    });
    apiMocks.getCandidateInvite.mockResolvedValue(candidateInvite());
    apiMocks.recordCandidateConsent.mockResolvedValue(consented);
    const user = userEvent.setup();
    render(<CandidateAssessment token="signed-token" />);

    const consent = await screen.findByRole("button", {
      name: "I consent and want to begin",
    });
    consent.focus();
    await user.keyboard("{Enter}");

    expect(
      await screen.findByRole("heading", {
        name: /which statements are most and least like you/i,
      }),
    ).toHaveFocus();
    expect(apiMocks.recordCandidateConsent).toHaveBeenCalledWith(
      "signed-token",
      "consent",
    );

    // A native radio group has one keyboard tab stop. For each block, choose
    // the first most-like option, then move the least-like group to its second
    // option with an arrow key. Tab past the skip choice to continue.
    for (let blockNumber = 1; blockNumber <= 6; blockNumber += 1) {
      await user.tab();
      expect(screen.getAllByRole("radio")[0]).toHaveFocus();
      await user.keyboard(" ");
      await user.tab();
      await user.keyboard("{ArrowDown}");
      await user.tab();
      await user.tab();
      if (blockNumber > 1) await user.tab();
      await user.keyboard("{Enter}");

      if (blockNumber < 6) {
        expect(
          await screen.findByText("Block " + String(blockNumber + 1) + " of 6"),
        ).toBeInTheDocument();
      }
    }

    expect(
      await screen.findByRole("heading", { name: "Review your responses" }),
    ).toHaveFocus();
    const submit = screen.getByRole("button", {
      name: "Submit my responses",
    });
    submit.focus();
    await user.keyboard("{Enter}");

    expect(
      await screen.findByRole("heading", {
        name: "Your responses are complete",
      }),
    ).toHaveFocus();
    expect(
      screen.getByText(/does not make a hiring decision/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/do not show or create a single overall fit score/i),
    ).toBeInTheDocument();

    const storedValues = Object.values(window.localStorage);
    expect(storedValues.join(" ")).not.toMatch(
      /raw_score|fit_score|construct_scores/,
    );
    const completion = window.localStorage.getItem(
      "iopsych.candidate.v1." + INVITATION_ID + ".completion",
    );
    expect(completion).toContain('"answered_block_count":6');
    expect(completion).toContain('"assessment_definition_version":"1.0.0"');
    expect(completion).toContain('"responses"');
    expect(
      window.localStorage.getItem(
        "iopsych.candidate.v1." + INVITATION_ID + ".draft",
      ),
    ).toBeNull();
  });

  it("supports prefer-not-to-answer and resumes a saved contract snapshot", async () => {
    const consented = candidateInvite({
      can_start_assessment: true,
      decision: "consent",
      status: "consented",
    });
    apiMocks.getCandidateInvite.mockResolvedValue(consented);
    const user = userEvent.setup();
    const first = render(<CandidateAssessment token="signed-token" />);

    const skip = await screen.findByRole("checkbox", {
      name: "Prefer not to answer this block",
    });
    skip.focus();
    await user.keyboard(" ");
    const continueButton = screen.getByRole("button", {
      name: "Save and continue",
    });
    continueButton.focus();
    await user.keyboard("{Enter}");

    await waitFor(() => {
      expect(
        window.localStorage.getItem(
          "iopsych.candidate.v1." + INVITATION_ID + ".draft",
        ),
      ).toContain('"skipped":true');
    });
    first.unmount();
    render(<CandidateAssessment token="signed-token" />);

    expect(await screen.findByText("Saved on this device")).toBeInTheDocument();
    const previous = screen.getByRole("button", { name: "Previous block" });
    previous.focus();
    await user.keyboard("{Enter}");
    expect(
      screen.getByRole("checkbox", {
        name: "Prefer not to answer this block",
      }),
    ).toBeChecked();
  });

  it("records a decline without rendering questions", async () => {
    apiMocks.getCandidateInvite.mockResolvedValue(candidateInvite());
    apiMocks.recordCandidateConsent.mockResolvedValue(
      candidateInvite({
        decision: "decline",
        decision_recorded_at: "2026-09-27T12:00:00Z",
        status: "declined",
      }),
    );
    const user = userEvent.setup();
    render(<CandidateAssessment token="signed-token" />);

    const decline = await screen.findByRole("button", { name: "I decline" });
    decline.focus();
    await user.keyboard("{Enter}");

    expect(
      await screen.findByRole("heading", {
        name: "You declined the assessment",
      }),
    ).toHaveFocus();
    expect(screen.queryAllByRole("radio")).toHaveLength(0);
    expect(
      screen.getByText(/no assessment questions or responses/i),
    ).toBeInTheDocument();
  });

  it("focuses the first choice when a block is incomplete", async () => {
    apiMocks.getCandidateInvite.mockResolvedValue(
      candidateInvite({
        can_start_assessment: true,
        decision: "consent",
        status: "consented",
      }),
    );
    const user = userEvent.setup();
    render(<CandidateAssessment token="signed-token" />);

    const continueButton = await screen.findByRole("button", {
      name: "Save and continue",
    });
    continueButton.focus();
    await user.keyboard("{Enter}");

    expect(await screen.findByRole("alert")).toHaveTextContent(
      /choose one statement in each column/i,
    );
    await waitFor(() => expect(screen.getAllByRole("radio")[0]).toHaveFocus());
  });
});
