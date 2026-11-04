/** @vitest-environment jsdom */
import { PILOT_ASSESSMENT_DEFINITION_V1 as definition } from "@iopsych/shared";
import {
  LEGACY_V1_DEFINITION_SHA256,
  type CandidateDefinition,
} from "./candidate-contracts";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import {
  candidateStorage,
  clearCandidateDevice,
  completeCandidateAssessment,
  DEVICE_MAX_AGE_MS,
  loadCandidateCompletion,
  loadCandidateDraft,
  saveCandidateDraft,
} from "./candidate-storage";

const assigned: CandidateDefinition = {
  definition,
  assignment: {
    assessment_definition_id: definition.id as "work-preferences-pilot",
    assessment_definition_version: "1.0.0",
    scoring_version: "1.0.0",
    matching_algorithm_version: "1.0.0",
    definition_sha256: LEGACY_V1_DEFINITION_SHA256,
  },
};
const id = "11111111-1111-4111-8111-111111111111";
const draftKey = `iopsych.candidate.v1.${id}.draft`;
const completionKey = `iopsych.candidate.v1.${id}.completion`;
const responses = {
  assessment_definition_id: definition.id,
  assessment_definition_version: definition.version,
  responses: [
    {
      block_id: definition.blocks[0]!.id,
      skipped: true as const,
      most_like_item_id: null,
      least_like_item_id: null,
    },
  ],
};
beforeEach(() => {
  window.localStorage.clear();
});
afterEach(() => {
  vi.restoreAllMocks();
  vi.useRealTimers();
});

it("contains getter denial and reports removal denial", () => {
  vi.spyOn(window, "localStorage", "get").mockImplementation(() => {
    throw new Error("Denied");
  });
  expect(candidateStorage()).toBeNull();
  expect(loadCandidateDraft(null, id, undefined, assigned)).toBeNull();
  expect(clearCandidateDevice(null, id)).toBe(false);
});
it("removes stale answers on empty snapshots and quota failures", () => {
  saveCandidateDraft(localStorage, id, responses, assigned);
  saveCandidateDraft(
    localStorage,
    id,
    { ...responses, responses: [] },
    assigned,
  );
  expect(localStorage.getItem(draftKey)).toBeNull();
  saveCandidateDraft(localStorage, id, responses, assigned);
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
    throw new Error("Quota");
  });
  expect(() =>
    saveCandidateDraft(localStorage, id, responses, assigned),
  ).toThrow("Quota");
  expect(localStorage.getItem(draftKey)).toBeNull();
});
it("expires drafts by device age and invitation deadline and removes malformed data", () => {
  vi.useFakeTimers();
  saveCandidateDraft(localStorage, id, responses, assigned);
  vi.advanceTimersByTime(DEVICE_MAX_AGE_MS);
  expect(loadCandidateDraft(localStorage, id, undefined, assigned)).toBeNull();
  expect(localStorage.getItem(draftKey)).toBeNull();
  saveCandidateDraft(localStorage, id, responses, assigned);
  expect(
    loadCandidateDraft(
      localStorage,
      id,
      new Date(Date.now() - 1).toISOString(),
      assigned,
    ),
  ).toBeNull();
  localStorage.setItem(draftKey, "invalid");
  expect(loadCandidateDraft(localStorage, id, undefined, assigned)).toBeNull();
  expect(localStorage.getItem(draftKey)).toBeNull();
});
it("purges legacy completions and stores only expiring answer-free receipts", () => {
  localStorage.setItem(
    completionKey,
    JSON.stringify({ response_set: responses }),
  );
  expect(loadCandidateCompletion(localStorage, id)).toBeNull();
  expect(localStorage.getItem(completionKey)).toBeNull();
  saveCandidateDraft(localStorage, id, responses, assigned);
  const receipt = completeCandidateAssessment(localStorage, id, responses, id);
  expect(Object.keys(receipt).sort()).toEqual([
    "assessment_id",
    "submitted_at",
  ]);
  expect(localStorage.getItem(draftKey)).toBeNull();
  expect(loadCandidateCompletion(localStorage, id)).toEqual(receipt);
  vi.useFakeTimers();
  vi.advanceTimersByTime(DEVICE_MAX_AGE_MS);
  expect(loadCandidateCompletion(localStorage, id)).toBeNull();
  expect(localStorage.getItem(completionKey)).toBeNull();
});
it("retains the in-memory receipt and clears answers when receipt writes fail", () => {
  saveCandidateDraft(localStorage, id, responses, assigned);
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
    throw new Error("Quota");
  });
  expect(
    completeCandidateAssessment(localStorage, id, responses, id).assessment_id,
  ).toBe(id);
  expect(localStorage.getItem(draftKey)).toBeNull();
});
it("attempts both removals and truthfully reports failure", () => {
  const remove = vi
    .spyOn(Storage.prototype, "removeItem")
    .mockImplementation(() => {
      throw new Error("Denied");
    });
  expect(clearCandidateDevice(localStorage, id)).toBe(false);
  expect(remove).toHaveBeenCalledTimes(2);
});

it("restores frozen hashless v1 only, rejecting unknown versions, IDs, items and different hashes", () => {
  const legacy = {
    saved_at: new Date().toISOString(),
    response_set: responses,
  };
  const put = (value: unknown) =>
    localStorage.setItem(draftKey, JSON.stringify(value));
  put(legacy);
  expect(
    loadCandidateDraft(localStorage, id, undefined, assigned)?.response_set,
  ).toEqual(responses);
  const changed = {
    ...assigned,
    assignment: { ...assigned.assignment, definition_sha256: "a".repeat(64) },
  };
  put(legacy);
  expect(loadCandidateDraft(localStorage, id, undefined, changed)).toBeNull();
  for (const patch of [
    { assessment_definition_version: "9.0.0" },
    { assessment_definition_id: "unknown" },
    { responses: [{ ...responses.responses[0], block_id: "unknown" }] },
  ]) {
    put({ ...legacy, response_set: { ...responses, ...patch } });
    expect(
      loadCandidateDraft(localStorage, id, undefined, assigned),
    ).toBeNull();
  }
  put({
    ...legacy,
    response_set: {
      ...responses,
      responses: [
        {
          block_id: "block-1",
          skipped: false,
          most_like_item_id: "unknown",
          least_like_item_id: "also-unknown",
        },
      ],
    },
  });
  expect(loadCandidateDraft(localStorage, id, undefined, assigned)).toBeNull();
});
it("binds new drafts to the exact hash and rejects mismatched writes", () => {
  const changed = {
    ...assigned,
    assignment: { ...assigned.assignment, definition_sha256: "b".repeat(64) },
  };
  saveCandidateDraft(localStorage, id, responses, changed);
  expect(
    loadCandidateDraft(localStorage, id, undefined, changed)?.definition_sha256,
  ).toBe("b".repeat(64));
  expect(loadCandidateDraft(localStorage, id, undefined, assigned)).toBeNull();
  expect(localStorage.getItem(draftKey)).toBeNull();
  expect(() =>
    saveCandidateDraft(
      localStorage,
      id,
      { ...responses, assessment_definition_version: "99.0.0" },
      assigned,
    ),
  ).toThrow("Draft assignment mismatch");
});
