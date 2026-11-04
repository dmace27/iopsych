/** @vitest-environment jsdom */

import "@testing-library/jest-dom/vitest";
import {
  act,
  cleanup,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
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
import { ApiClientError } from "../../../../lib/api-client";

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

  it("counts only complete or skipped blocks and retains progress when revisiting", async () => {
    apiMocks.getCandidateInvite.mockResolvedValue(
      candidateInvite({ can_start_assessment: true, decision: "consent" }),
    );
    const user = userEvent.setup();
    render(<CandidateAssessment token="signed-token" />);
    const progress = await screen.findByRole("progressbar", {
      name: "Blocks ready to submit",
    });
    expect(progress).toHaveAttribute("aria-valuenow", "0");
    const radios = screen.getAllByRole("radio");
    await user.click(radios[0]!);
    expect(progress).toHaveAttribute("aria-valuenow", "0");
    await user.click(radios[3]!);
    expect(progress).toHaveAttribute("aria-valuenow", "1");
    await user.click(screen.getByRole("button", { name: "Continue" }));
    expect(screen.getByText("Block 2 of 6")).toBeInTheDocument();
    expect(progress).toHaveAttribute("aria-valuenow", "1");
    await user.click(screen.getByRole("button", { name: "Previous block" }));
    expect(screen.getAllByRole("radio")[0]).toBeChecked();
    await user.click(screen.getAllByRole("radio")[2]!);
    expect(progress).toHaveAttribute("aria-valuenow", "0");
    await user.click(screen.getByRole("checkbox"));
    expect(progress).toHaveAttribute("aria-valuenow", "1");
  });

  it("shows the actual selected statements on review and returns to them for changes", async () => {
    apiMocks.getCandidateInvite.mockResolvedValue(
      candidateInvite({ can_start_assessment: true, decision: "consent" }),
    );
    const user = userEvent.setup();
    render(<CandidateAssessment token="signed-token" />);
    await screen.findByRole("checkbox");
    const radios = screen.getAllByRole("radio");
    const most = radios[0]!
      .getAttribute("aria-label")!
      .replace("Most like me: ", "");
    const least = radios[3]!
      .getAttribute("aria-label")!
      .replace("Least like me: ", "");
    await user.click(radios[0]!);
    await user.click(radios[3]!);
    await user.click(screen.getByRole("button", { name: "Continue" }));
    for (let index = 1; index < 6; index++) {
      await user.click(screen.getByRole("checkbox"));
      await user.click(
        screen.getByRole("button", {
          name: index === 5 ? "Review answers" : "Continue",
        }),
      );
    }
    const firstRow = within(screen.getAllByRole("listitem")[0]!);
    expect(firstRow.getByText(most)).toBeInTheDocument();
    expect(firstRow.getByText(least)).toBeInTheDocument();
    expect(apiMocks.submitCandidateAssessment).not.toHaveBeenCalled();
    await user.click(firstRow.getByRole("button", { name: "Change block 1" }));
    expect(screen.getAllByRole("radio")[0]).toBeChecked();
    expect(screen.getAllByRole("radio")[3]).toBeChecked();
    expect(
      screen.getByRole("heading", { name: /which statements/i }),
    ).toHaveFocus();
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

  it.each(["consent", "decline"] as const)(
    "requires manual reload and a fresh %s choice after a notice conflict",
    async (decision) => {
      const user = userEvent.setup();
      const original = candidateInvite({
        notice_sha256: "a".repeat(64),
        notice_history: "not_recorded",
      });
      const refreshed = candidateInvite({
        notice_sha256: "b".repeat(64),
        consent_notice: {
          ...original.consent_notice,
          retention: "The frozen retention notice.",
        },
      });
      apiMocks.getCandidateInvite
        .mockResolvedValueOnce(original)
        .mockResolvedValueOnce(refreshed);
      apiMocks.recordCandidateConsent
        .mockRejectedValueOnce(
          new ApiClientError("Review required", {
            status: 409,
            code: "notice_review_required",
          }),
        )
        .mockResolvedValueOnce(
          candidateInvite({
            decision,
            can_start_assessment: decision === "consent",
            status: decision === "consent" ? "consented" : "declined",
          }),
        );
      render(<CandidateAssessment token="signed-token" />);
      const choiceName =
        decision === "consent" ? "I consent and want to begin" : "I decline";
      await user.click(await screen.findByRole("button", { name: choiceName }));
      expect(apiMocks.recordCandidateConsent).toHaveBeenLastCalledWith(
        "signed-token",
        decision,
        original.notice_sha256,
      );
      expect(await screen.findByRole("alert")).toHaveTextContent(
        "Your choice was not recorded",
      );
      expect(apiMocks.getCandidateInvite).toHaveBeenCalledTimes(1);
      expect(apiMocks.getCandidateDefinition).not.toHaveBeenCalled();
      expect(
        screen.queryByRole("button", { name: choiceName }),
      ).not.toBeInTheDocument();
      await user.click(screen.getByRole("button", { name: "Reload notice" }));
      expect(
        await screen.findByText("The frozen retention notice."),
      ).toBeInTheDocument();
      expect(
        screen.getByRole("heading", { name: "Your choice and your data" }),
      ).toHaveFocus();
      expect(apiMocks.recordCandidateConsent).toHaveBeenCalledTimes(1);
      expect(apiMocks.getCandidateDefinition).not.toHaveBeenCalled();
      expect(localStorage.length).toBe(0);
      await user.click(screen.getByRole("button", { name: choiceName }));
      expect(apiMocks.recordCandidateConsent).toHaveBeenCalledTimes(2);
      expect(apiMocks.recordCandidateConsent).toHaveBeenLastCalledWith(
        "signed-token",
        decision,
        refreshed.notice_sha256,
      );
      if (decision === "consent") await screen.findByText("Block 1 of 6");
      else
        await screen.findByRole("heading", {
          name: "You declined the assessment",
        });
    },
  );

  it("keeps questions and decisions unavailable when notice reload fails", async () => {
    apiMocks.getCandidateInvite
      .mockResolvedValueOnce(candidateInvite({ notice_sha256: "a".repeat(64) }))
      .mockRejectedValueOnce(new Error("Reload unavailable"));
    apiMocks.recordCandidateConsent.mockRejectedValueOnce(
      new ApiClientError("Review required", {
        status: 409,
        code: "notice_review_required",
      }),
    );
    const user = userEvent.setup();
    render(<CandidateAssessment token="signed-token" />);
    await user.click(await screen.findByRole("button", { name: "I decline" }));
    await user.click(
      await screen.findByRole("button", { name: "Reload notice" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Reload unavailable",
    );
    expect(apiMocks.recordCandidateConsent).toHaveBeenCalledTimes(1);
    expect(apiMocks.getCandidateDefinition).not.toHaveBeenCalled();
    expect(
      screen.queryByRole("button", { name: "I decline" }),
    ).not.toBeInTheDocument();
  });

  it.each([
    [
      "legacy_unknown",
      "The notice associated with your earlier choice was not recorded.",
    ],
    [
      "legacy_unverified",
      "Your choice was recorded without a notice digest from the client.",
    ],
  ] as const)(
    "describes %s history factually",
    async (notice_history, message) => {
      apiMocks.getCandidateInvite.mockResolvedValue(
        candidateInvite({
          decision: "decline",
          status: "declined",
          notice_sha256: null,
          notice_history,
        }),
      );
      render(<CandidateAssessment token="signed-token" />);
      expect(
        await screen.findByText(message, { exact: false }),
      ).toBeInTheDocument();
      expect(apiMocks.recordCandidateConsent).not.toHaveBeenCalled();
      expect(apiMocks.getCandidateDefinition).not.toHaveBeenCalled();
    },
  );

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
      undefined,
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
    // Let the initial screen-focus effect finish before taking keyboard focus.
    await waitFor(() => {
      expect(
        screen.getByRole("heading", {
          name: /which statements are most and least like you/i,
        }),
      ).toHaveFocus();
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
    await waitFor(() =>
      expect(
        screen.getByRole("heading", {
          name: /which statements are most and least like you/i,
        }),
      ).toHaveFocus(),
    );
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
  it("restarts at block one with no stale choices or errors after clearing from review", async () => {
    apiMocks.getCandidateInvite.mockResolvedValue(
      candidateInvite({ can_start_assessment: true, decision: "consent" }),
    );
    apiMocks.submitCandidateAssessment.mockRejectedValueOnce(
      new Error("Old submission error"),
    );
    const user = userEvent.setup();
    render(<CandidateAssessment token="signed-token" />);
    for (let index = 0; index < 6; index++) {
      await user.click(await screen.findByRole("checkbox"));
      await user.click(
        screen.getByRole("button", {
          name: index === 5 ? "Review answers" : "Continue",
        }),
      );
    }
    await user.click(
      screen.getByRole("button", { name: "Submit my responses" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Old submission error",
    );
    await user.click(screen.getByRole("button", { name: "Clear device data" }));
    expect(
      screen.getByRole("heading", { name: "Assessment paused" }),
    ).toHaveFocus();
    expect(
      localStorage.getItem(`iopsych.candidate.v1.${INVITATION_ID}.draft`),
    ).toBeNull();
    await user.click(
      screen.getByRole("button", { name: "Continue assessment" }),
    );
    expect(screen.getByText("Block 1 of 6")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", {
        name: /which statements are most and least like you/i,
      }),
    ).toHaveFocus();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(
      screen.queryByText(/All six blocks are ready/),
    ).not.toBeInTheDocument();
    expect(screen.queryByText(/Device data cleared/)).not.toBeInTheDocument();
    expect(screen.getByText("Not saved yet")).toBeInTheDocument();
    for (let index = 0; index < 6; index++) {
      expect(screen.getByRole("checkbox")).not.toBeChecked();
      for (const radio of screen.getAllByRole("radio"))
        expect(radio).not.toBeChecked();
      if (index === 0) {
        await user.click(screen.getByRole("button", { name: "Continue" }));
        expect(await screen.findByRole("alert")).toHaveTextContent(
          /choose one statement/i,
        );
      }
      await user.click(screen.getByRole("checkbox"));
      await user.click(
        screen.getByRole("button", {
          name: index === 5 ? "Review answers" : "Continue",
        }),
      );
    }
    expect(
      screen.getByRole("heading", { name: "Review your responses" }),
    ).toHaveFocus();
    await user.click(
      screen.getByRole("button", { name: "Submit my responses" }),
    );
    expect(
      await screen.findByRole("heading", {
        name: "Your responses are complete",
      }),
    ).toBeInTheDocument();
  });

  it("immediately removes preexisting answers and receipts on acknowledged decline", async () => {
    apiMocks.getCandidateInvite.mockResolvedValue(candidateInvite());
    apiMocks.recordCandidateConsent.mockResolvedValue(
      candidateInvite({ decision: "decline", status: "declined" }),
    );
    const draftKey = `iopsych.candidate.v1.${INVITATION_ID}.draft`;
    const completionKey = `iopsych.candidate.v1.${INVITATION_ID}.completion`;
    localStorage.setItem(
      draftKey,
      JSON.stringify({
        saved_at: new Date().toISOString(),
        response_set: {
          assessment_definition_id: PILOT_ASSESSMENT_DEFINITION_V1.id,
          assessment_definition_version: PILOT_ASSESSMENT_DEFINITION_V1.version,
          responses: [
            {
              block_id: "block-1",
              skipped: true,
              most_like_item_id: null,
              least_like_item_id: null,
            },
          ],
        },
      }),
    );
    render(<CandidateAssessment token="signed-token" />);
    const decline = await screen.findByRole("button", { name: "I decline" });
    expect(localStorage.getItem(draftKey)).not.toBeNull();
    localStorage.setItem(
      completionKey,
      JSON.stringify({
        assessment_id: INVITATION_ID,
        submitted_at: new Date().toISOString(),
      }),
    );
    await userEvent.setup().click(decline);
    expect(
      await screen.findByRole("heading", {
        name: "You declined the assessment",
      }),
    ).toHaveFocus();
    expect(localStorage.getItem(draftKey)).toBeNull();
    expect(localStorage.getItem(completionKey)).toBeNull();
    expect(apiMocks.getCandidateDefinition).not.toHaveBeenCalled();
  });

  it("hides the old assignment and choices immediately when the invitation token changes", async () => {
    apiMocks.getCandidateInvite.mockResolvedValueOnce(
      candidateInvite({ can_start_assessment: true, decision: "consent" }),
    );
    const user = userEvent.setup();
    const page = render(<CandidateAssessment token="old-token" />);
    await user.click(await screen.findByRole("checkbox"));
    await user.click(screen.getByRole("button", { name: "Continue" }));
    let resolveInvite!: (value: CandidateInvite) => void;
    apiMocks.getCandidateInvite.mockReturnValueOnce(
      new Promise<CandidateInvite>((resolve) => {
        resolveInvite = resolve;
      }),
    );
    page.rerender(<CandidateAssessment token="new-token" />);
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
    expect(screen.getByText("Opening invitation…")).toBeInTheDocument();
    await act(async () =>
      resolveInvite(
        candidateInvite({
          invitation_id: "22222222-2222-4222-8222-222222222222",
          can_start_assessment: true,
          decision: "consent",
        }),
      ),
    );
    expect(await screen.findByText("Block 1 of 6")).toBeInTheDocument();
    expect(screen.getByRole("checkbox")).not.toBeChecked();
    expect(
      localStorage.getItem(
        "iopsych.candidate.v1.22222222-2222-4222-8222-222222222222.draft",
      ),
    ).toBeNull();
  });

  it.each(["consent", "definition"])(
    "ignores an old pending %s response after a token change",
    async (pendingStage) => {
      apiMocks.getCandidateInvite.mockResolvedValue(candidateInvite());
      const consented = candidateInvite({
        can_start_assessment: true,
        decision: "consent",
      });
      let finish!: () => void;
      if (pendingStage === "consent") {
        apiMocks.recordCandidateConsent.mockReturnValueOnce(
          new Promise((resolve) => {
            finish = () => resolve(consented);
          }),
        );
      } else {
        apiMocks.recordCandidateConsent.mockResolvedValueOnce(consented);
        const pinned = await apiMocks.getCandidateDefinition();
        apiMocks.getCandidateDefinition.mockClear();
        apiMocks.getCandidateDefinition.mockReturnValueOnce(
          new Promise((resolve) => {
            finish = () => resolve(pinned);
          }),
        );
      }
      const page = render(<CandidateAssessment token="old-token" />);
      await userEvent.setup().click(
        await screen.findByRole("button", {
          name: "I consent and want to begin",
        }),
      );
      apiMocks.getCandidateInvite.mockResolvedValueOnce(
        candidateInvite({
          invitation_id: "22222222-2222-4222-8222-222222222222",
          role_title: "New invitation role",
        }),
      );
      page.rerender(<CandidateAssessment token="new-token" />);
      await screen.findByText("New invitation role");
      await act(async () => finish());
      expect(
        screen.getByRole("heading", { name: "Your choice and your data" }),
      ).toBeInTheDocument();
      expect(screen.getByText("New invitation role")).toBeInTheDocument();
      expect(screen.queryByRole("radio")).not.toBeInTheDocument();
      expect(apiMocks.getCandidateDefinition).toHaveBeenCalledTimes(
        pendingStage === "consent" ? 0 : 1,
      );
      expect(localStorage.length).toBe(0);
    },
  );
  it("does not apply an old submission receipt to a new invitation", async () => {
    apiMocks.getCandidateInvite.mockResolvedValueOnce(
      candidateInvite({ can_start_assessment: true, decision: "consent" }),
    );
    localStorage.setItem(
      `iopsych.candidate.v1.${INVITATION_ID}.draft`,
      JSON.stringify({
        saved_at: new Date().toISOString(),
        response_set: {
          assessment_definition_id: PILOT_ASSESSMENT_DEFINITION_V1.id,
          assessment_definition_version: PILOT_ASSESSMENT_DEFINITION_V1.version,
          responses: PILOT_ASSESSMENT_DEFINITION_V1.blocks.map((block) => ({
            block_id: block.id,
            skipped: true,
            most_like_item_id: null,
            least_like_item_id: null,
          })),
        },
      }),
    );
    let finish!: () => void;
    apiMocks.submitCandidateAssessment.mockReturnValueOnce(
      new Promise((resolve) => {
        finish = () => resolve({ assessment_id: INVITATION_ID });
      }),
    );
    const user = userEvent.setup();
    const page = render(<CandidateAssessment token="old-token" />);
    await user.click(
      await screen.findByRole("button", { name: "Review answers" }),
    );
    await user.click(
      screen.getByRole("button", { name: "Submit my responses" }),
    );
    expect(screen.getByRole("button", { name: "Submitting…" })).toBeDisabled();
    apiMocks.getCandidateInvite.mockResolvedValueOnce(
      candidateInvite({
        invitation_id: "22222222-2222-4222-8222-222222222222",
        can_start_assessment: true,
        decision: "consent",
      }),
    );
    page.rerender(<CandidateAssessment token="new-token" />);
    await screen.findByText("Block 1 of 6");
    await act(async () => finish());
    expect(screen.getByText("Block 1 of 6")).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "Your responses are complete" }),
    ).not.toBeInTheDocument();
    expect(
      localStorage.getItem(`iopsych.candidate.v1.${INVITATION_ID}.completion`),
    ).toBeNull();
    expect(
      localStorage.getItem(
        "iopsych.candidate.v1.22222222-2222-4222-8222-222222222222.completion",
      ),
    ).toBeNull();
    await user.click(screen.getByRole("checkbox"));
    expect(screen.getByRole("checkbox")).toBeChecked();
    expect(apiMocks.submitCandidateAssessment).toHaveBeenCalledTimes(1);
    expect(apiMocks.submitCandidateAssessment).toHaveBeenCalledWith(
      "old-token",
      expect.objectContaining({ responses: expect.any(Array) }),
    );
  });
});
