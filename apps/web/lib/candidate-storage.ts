import type { AssessmentResponseSet } from "@iopsych/shared";
import { z } from "zod";

import {
  CandidateDraftSchema,
  LEGACY_V1_DEFINITION_SHA256,
  type CandidateDefinition,
  type CandidateDraft,
} from "./candidate-contracts";

const STORAGE_PREFIX = "iopsych.candidate.v1";
// Device recovery limit, not a server retention policy. Cleanup occurs on access.
export const DEVICE_MAX_AGE_MS = 24 * 60 * 60 * 1000;
const ReceiptSchema = z.strictObject({
  assessment_id: z.uuid(),
  submitted_at: z.string().datetime(),
});
export type DeviceReceipt = z.infer<typeof ReceiptSchema>;
const key = (id: string, kind: string) => `${STORAGE_PREFIX}.${id}.${kind}`;

/** Access itself can throw in restricted browser contexts. */
export function candidateStorage(): Storage | null {
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

function fresh(timestamp: string, expiresAt?: string): boolean {
  const time = Date.parse(timestamp);
  const now = Date.now();
  return (
    time <= now &&
    now - time < DEVICE_MAX_AGE_MS &&
    (expiresAt === undefined || now < Date.parse(expiresAt))
  );
}

export function clearCandidateDevice(
  storage: Storage | null,
  id: string,
): boolean {
  if (!storage) return false;
  let cleared = true;
  for (const kind of ["draft", "completion"]) {
    try {
      storage.removeItem(key(id, kind));
    } catch {
      cleared = false;
    }
  }
  return cleared;
}

export function loadCandidateDraft(
  storage: Storage | null,
  id: string,
  expiresAt: string | undefined,
  assigned: CandidateDefinition,
): CandidateDraft | null {
  if (!storage) return null;
  try {
    const raw = storage.getItem(key(id, "draft"));
    if (raw === null) return null;
    const parsed = CandidateDraftSchema.safeParse(JSON.parse(raw));
    if (
      parsed.success &&
      fresh(parsed.data.saved_at, expiresAt) &&
      draftMatchesAssignment(parsed.data, assigned)
    )
      return parsed.data;
  } catch {
    /* Invalid or inaccessible state must not block the invitation. */
  }
  try {
    storage.removeItem(key(id, "draft"));
  } catch {
    /* Best effort. */
  }
  return null;
}

export function saveCandidateDraft(
  storage: Storage | null,
  id: string,
  responseSet: AssessmentResponseSet,
  assigned: CandidateDefinition,
): CandidateDraft {
  const draft = CandidateDraftSchema.parse({
    definition_sha256: assigned.assignment.definition_sha256,
    response_set: responseSet,
    saved_at: new Date().toISOString(),
  });
  if (!draftMatchesAssignment(draft, assigned))
    throw new Error("Draft assignment mismatch");
  if (!storage) throw new Error("Device storage unavailable");
  // Remove first: a failed replacement must not resurrect older complete choices.
  storage.removeItem(key(id, "draft"));
  if (responseSet.responses.length)
    storage.setItem(key(id, "draft"), JSON.stringify(draft));
  return draft;
}

/** Only an acknowledged server ID and timestamp are stored, never answers. */
export function completeCandidateAssessment(
  storage: Storage | null,
  id: string,
  _responseSet: AssessmentResponseSet,
  assessmentId: string,
): DeviceReceipt {
  const receipt = ReceiptSchema.parse({
    assessment_id: assessmentId,
    submitted_at: new Date().toISOString(),
  });
  clearCandidateDevice(storage, id);
  try {
    storage?.setItem(key(id, "completion"), JSON.stringify(receipt));
  } catch {
    /* Server acknowledgement remains authoritative. */
  }
  return receipt;
}

/** Purge old answer-bearing completions; receipts never authorize completion. */
export function loadCandidateCompletion(
  storage: Storage | null,
  id: string,
  expiresAt?: string,
): DeviceReceipt | null {
  if (!storage) return null;
  try {
    const raw = storage.getItem(key(id, "completion"));
    if (raw === null) return null;
    const parsed = ReceiptSchema.safeParse(JSON.parse(raw));
    if (parsed.success && fresh(parsed.data.submitted_at, expiresAt))
      return parsed.data;
  } catch {
    /* Best effort cleanup below. */
  }
  try {
    storage.removeItem(key(id, "completion"));
  } catch {
    /* Best effort. */
  }
  return null;
}

/** Hashless drafts are recognized only as the exact frozen legacy assignment. */
function draftMatchesAssignment(
  draft: CandidateDraft,
  { assignment, definition }: CandidateDefinition,
): boolean {
  const response = draft.response_set;
  if (
    response.assessment_definition_id !== assignment.assessment_definition_id ||
    response.assessment_definition_version !==
      assignment.assessment_definition_version
  )
    return false;
  if (draft.definition_sha256 !== undefined) {
    if (draft.definition_sha256 !== assignment.definition_sha256) return false;
  } else if (
    assignment.assessment_definition_id !== "work-preferences-pilot" ||
    assignment.assessment_definition_version !== "1.0.0" ||
    assignment.definition_sha256 !== LEGACY_V1_DEFINITION_SHA256
  )
    return false;
  return response.responses.every((choice) => {
    const block = definition.blocks.find(({ id }) => id === choice.block_id);
    return (
      block !== undefined &&
      (choice.skipped ||
        (block.items.some(({ id }) => id === choice.most_like_item_id) &&
          block.items.some(({ id }) => id === choice.least_like_item_id)))
    );
  });
}
