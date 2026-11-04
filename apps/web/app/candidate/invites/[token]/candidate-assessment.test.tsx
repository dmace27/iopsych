/** @vitest-environment jsdom */

import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { PILOT_ASSESSMENT_DEFINITION_V1 } from "@iopsych/shared";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const apiMocks = vi.hoisted(() => ({
  getCandidateInvite: vi.fn(),
  getCandidateDefinition: vi.fn(),
  recordCandidateConsent: vi.fn(),
  submitCandidateAssessment: vi.fn(),
}));

vi.mock("../../../../lib/candidate-api", () => apiMocks);

import {
  LEGACY_V1_DEFINITION_SHA256,
  type CandidateInvite,
} from "../../../../lib/candidate-contracts";
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
    expires_at: "2099-10-01T16:00:00Z",
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
    apiMocks.getCandidateDefinition.mockReset().mockResolvedValue({
      assignment: {
        assessment_definition_id: PILOT_ASSESSMENT_DEFINITION_V1.id,
        assessment_definition_version: "1.0.0",
        scoring_version: "1.0.0",
        matching_algorithm_version: "1.0.0",
        definition_sha256: LEGACY_V1_DEFINITION_SHA256,
      },
      definition: PILOT_ASSESSMENT_DEFINITION_V1,
    });
    apiMocks.recordCandidateConsent.mockReset();
    apiMocks.submitCandidateAssessment.mockReset();
    apiMocks.submitCandidateAssessment.mockResolvedValue({
      assessment_id: INVITATION_ID,
    });
    window.localStorage.clear();
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("does not expose any assessment question before affirmative consent", async () => {
    apiMocks.getCandidateInvite.mockResolvedValue(candidateInvite());
    render(<CandidateAssessment token="signed-token" />);

    expect(
      await screen.findByRole("heading", {
        name: "Your choice and your data",
      }),
    ).toBeInTheDocument();
    expect(apiMocks.getCandidateDefinition).not.toHaveBeenCalled();
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

  it("does not fetch a definition before consent or after decline", async () => {
    apiMocks.getCandidateInvite.mockResolvedValue(
      candidateInvite({ decision: "decline", status: "declined" }),
    );
    render(<CandidateAssessment token="signed-token" />);
    await screen.findByText("You declined the assessment");
    expect(apiMocks.getCandidateDefinition).not.toHaveBeenCalled();
  });

  it("fails closed on unavailable assignments and retries without using bundled questions", async () => {
    apiMocks.getCandidateInvite.mockResolvedValue(
      candidateInvite({
        decision: "consent",
        can_start_assessment: true,
        status: "consented",
      }),
    );
    apiMocks.getCandidateDefinition.mockRejectedValueOnce(
      new Error("Unsupported assessment version"),
    );
    render(<CandidateAssessment token="signed-token" />);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Unsupported assessment version",
    );
    expect(screen.queryByRole("radio")).not.toBeInTheDocument();
    expect(localStorage.length).toBe(0);
    const pinned = structuredClone(PILOT_ASSESSMENT_DEFINITION_V1);
    pinned.blocks[0]!.items[0]!.statement = "The pinned historical statement.";
    apiMocks.getCandidateDefinition.mockResolvedValue({
      definition: pinned,
      assignment: {
        assessment_definition_id: pinned.id,
        assessment_definition_version: pinned.version,
        scoring_version: "1.0.0",
        matching_algorithm_version: "1.0.0",
        definition_sha256: "c".repeat(64),
      },
    });
    await userEvent
      .setup()
      .click(screen.getByRole("button", { name: "Try again" }));
    expect(
      await screen.findByText("The pinned historical statement."),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(
        PILOT_ASSESSMENT_DEFINITION_V1.blocks[0]!.items[0]!.statement,
      ),
    ).not.toBeInTheDocument();
    await userEvent.setup().click(screen.getByRole("checkbox"));
    expect(
      JSON.parse(
        localStorage.getItem(`iopsych.candidate.v1.${INVITATION_ID}.draft`)!,
      ).definition_sha256,
    ).toBe("c".repeat(64));
  });

  it("restores a hashless historical v1 draft and upgrades its envelope", async () => {
    const response = {
      block_id: "block-1",
      skipped: true,
      most_like_item_id: null,
      least_like_item_id: null,
    };
    localStorage.setItem(
      `iopsych.candidate.v1.${INVITATION_ID}.draft`,
      JSON.stringify({
        saved_at: new Date().toISOString(),
        response_set: {
          assessment_definition_id: "work-preferences-pilot",
          assessment_definition_version: "1.0.0",
          responses: [response],
        },
      }),
    );
    apiMocks.getCandidateInvite.mockResolvedValue(
      candidateInvite({
        decision: "consent",
        can_start_assessment: true,
        status: "consented",
      }),
    );
    render(<CandidateAssessment token="signed-token" />);
    expect(await screen.findByText("Block 2 of 6")).toBeInTheDocument();
    await waitFor(() =>
      expect(
        JSON.parse(
          localStorage.getItem(`iopsych.candidate.v1.${INVITATION_ID}.draft`)!,
        ).definition_sha256,
      ).toBe(LEGACY_V1_DEFINITION_SHA256),
    );
    await userEvent
      .setup()
      .click(screen.getByRole("button", { name: "Previous block" }));
    expect(screen.getByRole("checkbox")).toBeChecked();
  });

  it("does not render questions when the definition fetch fails after consent", async () => {
    apiMocks.getCandidateInvite.mockResolvedValue(candidateInvite());
    apiMocks.recordCandidateConsent.mockResolvedValue(
      candidateInvite({
        decision: "consent",
        can_start_assessment: true,
        status: "consented",
      }),
    );
    apiMocks.getCandidateDefinition.mockRejectedValue(
      new Error("Definition unavailable"),
    );
    render(<CandidateAssessment token="signed-token" />);
    await userEvent.setup().click(
      await screen.findByRole("button", {
        name: "I consent and want to begin",
      }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Definition unavailable",
    );
    expect(screen.queryByRole("radio")).not.toBeInTheDocument();
    expect(localStorage.length).toBe(0);
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
    await waitFor(() =>
      expect(
        screen.getByRole("heading", { name: "Your choice and your data" }),
      ).toHaveFocus(),
    );
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
    expect(
      screen.getAllByRole("link", {
        name: /data-rights contact|request a copy, correction, or deletion/i,
      })[0],
    ).toHaveAttribute("href", expect.stringContaining(INVITATION_ID));

    const storedValues = Object.values(window.localStorage);
    expect(storedValues.join(" ")).not.toMatch(
      /raw_score|fit_score|construct_scores/,
    );
    const completion = window.localStorage.getItem(
      "iopsych.candidate.v1." + INVITATION_ID + ".completion",
    );
    expect(completion).not.toContain('"answered_block_count"');
    expect(completion).not.toContain('"assessment_definition_version"');
    expect(completion).not.toContain('"responses"');
    expect(completion).toContain('"assessment_id"');
    expect(apiMocks.submitCandidateAssessment).toHaveBeenCalledWith(
      "signed-token",
      expect.objectContaining({ responses: expect.any(Array) }),
    );
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
      name: "Continue",
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
    await waitFor(() =>
      expect(
        screen.getByRole("heading", {
          name: /which statements are most and least like you/i,
        }),
      ).toHaveFocus(),
    );
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
      name: "Continue",
    });
    continueButton.focus();
    await user.keyboard("{Enter}");

    expect(await screen.findByRole("alert")).toHaveTextContent(
      /choose one statement in each column/i,
    );
    await waitFor(() => expect(screen.getAllByRole("radio")[0]).toHaveFocus());
  });

  it("purges legacy answers, requires server acknowledgement, and permits retries", async () => {
    apiMocks.getCandidateInvite.mockResolvedValue(
      candidateInvite({
        can_start_assessment: true,
        decision: "consent",
        status: "consented",
      }),
    );
    // Older completions were stored on this device without reaching the server.
    const definition = PILOT_ASSESSMENT_DEFINITION_V1;
    const legacy = {
      submitted_at: "2026-09-27T12:00:00Z",
      answered_block_count: 0,
      skipped_block_count: 6,
      response_set: {
        assessment_definition_id: definition.id,
        assessment_definition_version: definition.version,
        responses: definition.blocks.map((block) => ({
          block_id: block.id,
          skipped: true,
          most_like_item_id: null,
          least_like_item_id: null,
        })),
      },
    };
    window.localStorage.setItem(
      `iopsych.candidate.v1.${INVITATION_ID}.completion`,
      JSON.stringify(legacy),
    );
    apiMocks.submitCandidateAssessment.mockRejectedValueOnce(
      new Error("Network unavailable. Try again."),
    );
    const user = userEvent.setup();
    render(<CandidateAssessment token="signed-token" />);
    for (let index = 0; index < 6; index++) {
      await user.click(
        await screen.findByRole("checkbox", {
          name: "Prefer not to answer this block",
        }),
      );
      await user.click(
        screen.getByRole("button", {
          name: index === 5 ? "Review answers" : "Continue",
        }),
      );
    }
    expect(
      window.localStorage.getItem(
        `iopsych.candidate.v1.${INVITATION_ID}.completion`,
      ),
    ).toBeNull();
    await user.click(
      screen.getByRole("button", { name: "Submit my responses" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Network unavailable",
    );
    expect(
      screen.queryByRole("heading", { name: "Your responses are complete" }),
    ).not.toBeInTheDocument();
    expect(
      window.localStorage.getItem(
        `iopsych.candidate.v1.${INVITATION_ID}.completion`,
      ),
    ).toBeNull();
    await user.click(
      screen.getByRole("button", { name: "Submit my responses" }),
    );
    expect(
      await screen.findByRole("heading", {
        name: "Your responses are complete",
      }),
    ).toBeInTheDocument();
    expect(apiMocks.submitCandidateAssessment).toHaveBeenCalledTimes(2);
  });

  it("uses the server receipt to recognize submissions from another device", async () => {
    apiMocks.getCandidateInvite.mockResolvedValue(
      candidateInvite({
        can_start_assessment: true,
        decision: "consent",
        status: "consented",
        assessment_id: INVITATION_ID,
      }),
    );
    render(<CandidateAssessment token="signed-token" />);
    expect(
      await screen.findByRole("heading", {
        name: "Your responses are complete",
      }),
    ).toBeInTheDocument();
    expect(apiMocks.submitCandidateAssessment).not.toHaveBeenCalled();
    expect(screen.queryAllByRole("radio")).toHaveLength(0);
  });

  it("blocks edits during submission and completes when the storage getter throws", async () => {
    vi.spyOn(window, "localStorage", "get").mockImplementation(() => {
      throw new Error("Denied");
    });
    apiMocks.getCandidateInvite.mockResolvedValue(
      candidateInvite({
        can_start_assessment: true,
        decision: "consent",
        status: "consented",
      }),
    );
    const user = userEvent.setup();
    render(<CandidateAssessment token="signed-token" />);
    for (let index = 0; index < 6; index++) {
      await user.click(
        await screen.findByRole("checkbox", {
          name: "Prefer not to answer this block",
        }),
      );
      await user.click(
        screen.getByRole("button", {
          name: index === 5 ? "Review answers" : "Continue",
        }),
      );
    }
    let acknowledge = () => {};
    apiMocks.submitCandidateAssessment.mockReturnValueOnce(
      new Promise((resolve) => {
        acknowledge = () => resolve({ assessment_id: INVITATION_ID });
      }),
    );
    await user.click(
      screen.getByRole("button", { name: "Submit my responses" }),
    );
    expect(screen.getByRole("button", { name: "Submitting…" })).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Back to assessment" }),
    ).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Change block 1" }),
    ).toBeDisabled();
    expect(
      screen.queryByRole("heading", { name: "Your responses are complete" }),
    ).not.toBeInTheDocument();
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("Storage unavailable");
    });
    acknowledge();
    expect(
      await screen.findByRole("heading", {
        name: "Your responses are complete",
      }),
    ).toBeInTheDocument();
    expect(apiMocks.submitCandidateAssessment).toHaveBeenCalledTimes(1);
  });
  it("reports quota failure honestly and keeps save-exit on the current page", async () => {
    apiMocks.getCandidateInvite.mockResolvedValue(
      candidateInvite({ can_start_assessment: true, decision: "consent" }),
    );
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("Quota");
    });
    const user = userEvent.setup();
    render(<CandidateAssessment token="signed-token" />);
    await user.click(
      await screen.findByRole("checkbox", {
        name: "Prefer not to answer this block",
      }),
    );
    expect(
      await screen.findByText(
        "Not saved on this device. Keep this page open to finish.",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByText("Saved on this device")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Save and exit" }));
    expect(
      screen.getByText(/Could not save. Keep this page open/),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "Assessment paused" }),
    ).not.toBeInTheDocument();
  });

  it("removes a completed choice when edited to incomplete, including after reload", async () => {
    apiMocks.getCandidateInvite.mockResolvedValue(
      candidateInvite({ can_start_assessment: true, decision: "consent" }),
    );
    const user = userEvent.setup();
    const first = render(<CandidateAssessment token="signed-token" />);
    await screen.findByRole("checkbox");
    const radios = screen.getAllByRole("radio");
    await user.click(radios[0]!);
    await user.click(radios[3]!);
    expect(
      window.localStorage.getItem(
        `iopsych.candidate.v1.${INVITATION_ID}.draft`,
      ),
    ).not.toBeNull();
    await user.click(radios[2]!);
    expect(screen.getByText(/Partial block not saved/)).toBeInTheDocument();
    expect(
      window.localStorage.getItem(
        `iopsych.candidate.v1.${INVITATION_ID}.draft`,
      ),
    ).toBeNull();
    first.unmount();
    render(<CandidateAssessment token="signed-token" />);
    await screen.findByRole("checkbox");
    expect(
      screen
        .getAllByRole("radio")
        .every((radio) => !(radio as HTMLInputElement).checked),
    ).toBe(true);
  });

  it("pauses after saving and clears device data without autosaving it again", async () => {
    apiMocks.getCandidateInvite.mockResolvedValue(
      candidateInvite({ can_start_assessment: true, decision: "consent" }),
    );
    const user = userEvent.setup();
    render(<CandidateAssessment token="signed-token" />);
    await user.click(await screen.findByRole("checkbox"));
    await user.click(screen.getByRole("button", { name: "Save and exit" }));
    expect(
      screen.getByRole("heading", { name: "Assessment paused" }),
    ).toBeInTheDocument();
    expect(
      window.localStorage.getItem(
        `iopsych.candidate.v1.${INVITATION_ID}.draft`,
      ),
    ).not.toBeNull();
    await user.click(screen.getByRole("button", { name: "Clear device data" }));
    expect(
      screen.getByText("Device data cleared. You can close this window."),
    ).toBeInTheDocument();
    expect(
      window.localStorage.getItem(
        `iopsych.candidate.v1.${INVITATION_ID}.draft`,
      ),
    ).toBeNull();
    expect(screen.queryAllByRole("radio")).toHaveLength(0);
  });
});
