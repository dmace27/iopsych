/** @vitest-environment jsdom */
import { PILOT_ASSESSMENT_DEFINITION_V1 as definition } from "@iopsych/shared";
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
  expect(loadCandidateDraft(null, id)).toBeNull();
  expect(clearCandidateDevice(null, id)).toBe(false);
});
it("removes stale answers on empty snapshots and quota failures", () => {
  saveCandidateDraft(localStorage, id, responses);
  saveCandidateDraft(localStorage, id, { ...responses, responses: [] });
  expect(localStorage.getItem(draftKey)).toBeNull();
  saveCandidateDraft(localStorage, id, responses);
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
    throw new Error("Quota");
  });
  expect(() => saveCandidateDraft(localStorage, id, responses)).toThrow(
    "Quota",
  );
  expect(localStorage.getItem(draftKey)).toBeNull();
});
it("expires drafts by device age and invitation deadline and removes malformed data", () => {
  vi.useFakeTimers();
  saveCandidateDraft(localStorage, id, responses);
  vi.advanceTimersByTime(DEVICE_MAX_AGE_MS);
  expect(loadCandidateDraft(localStorage, id)).toBeNull();
  expect(localStorage.getItem(draftKey)).toBeNull();
  saveCandidateDraft(localStorage, id, responses);
  expect(
    loadCandidateDraft(
      localStorage,
      id,
      new Date(Date.now() - 1).toISOString(),
    ),
  ).toBeNull();
  localStorage.setItem(draftKey, "invalid");
  expect(loadCandidateDraft(localStorage, id)).toBeNull();
  expect(localStorage.getItem(draftKey)).toBeNull();
});
it("purges legacy completions and stores only expiring answer-free receipts", () => {
  localStorage.setItem(
    completionKey,
    JSON.stringify({ response_set: responses }),
  );
  expect(loadCandidateCompletion(localStorage, id)).toBeNull();
  expect(localStorage.getItem(completionKey)).toBeNull();
  saveCandidateDraft(localStorage, id, responses);
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
  saveCandidateDraft(localStorage, id, responses);
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
