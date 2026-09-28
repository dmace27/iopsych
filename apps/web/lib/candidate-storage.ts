import type { AssessmentResponseSet } from "@iopsych/shared";

import {
  CandidateCompletionSchema,
  CandidateDraftSchema,
  type CandidateCompletion,
  type CandidateDraft,
} from "./candidate-contracts";

const STORAGE_PREFIX = "iopsych.candidate.v1";

function draftKey(invitationId: string): string {
  return `${STORAGE_PREFIX}.${invitationId}.draft`;
}

function completionKey(invitationId: string): string {
  return `${STORAGE_PREFIX}.${invitationId}.completion`;
}

/** Ignore malformed or obsolete browser state instead of blocking an invite. */
export function loadCandidateDraft(
  storage: Storage,
  invitationId: string,
): CandidateDraft | null {
  try {
    const raw = storage.getItem(draftKey(invitationId));
    if (raw === null) return null;
    const parsed = CandidateDraftSchema.safeParse(JSON.parse(raw));
    return parsed.success ? parsed.data : null;
  } catch {
    return null;
  }
}

/** Persist only a shared-contract response snapshot, never a score. */
export function saveCandidateDraft(
  storage: Storage,
  invitationId: string,
  responseSet: AssessmentResponseSet,
): CandidateDraft {
  const draft = CandidateDraftSchema.parse({
    response_set: responseSet,
    saved_at: new Date().toISOString(),
  });
  storage.setItem(draftKey(invitationId), JSON.stringify(draft));
  return draft;
}

/** Replace draft state with a submitted response snapshot and score-free receipt. */
export function completeCandidateAssessment(
  storage: Storage,
  invitationId: string,
  responseSet: AssessmentResponseSet,
  assessmentId: string,
): CandidateCompletion {
  const skippedBlockCount = responseSet.responses.filter(
    ({ skipped }) => skipped,
  ).length;
  const completion = CandidateCompletionSchema.parse({
    assessment_id: assessmentId,
    answered_block_count: responseSet.responses.length - skippedBlockCount,
    response_set: responseSet,
    skipped_block_count: skippedBlockCount,
    submitted_at: new Date().toISOString(),
  });
  storage.setItem(completionKey(invitationId), JSON.stringify(completion));
  storage.removeItem(draftKey(invitationId));
  return completion;
}

/** Resume directly at completion after a reload on the same trusted device. */
export function loadCandidateCompletion(
  storage: Storage,
  invitationId: string,
): CandidateCompletion | null {
  try {
    const raw = storage.getItem(completionKey(invitationId));
    if (raw === null) return null;
    const parsed = CandidateCompletionSchema.safeParse(JSON.parse(raw));
    return parsed.success ? parsed.data : null;
  } catch {
    return null;
  }
}
