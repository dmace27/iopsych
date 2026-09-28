import { AssessmentResponseSetSchema } from "@iopsych/shared";
import { z } from "zod";

/** Invitation lifecycle values returned by the package 2B candidate API. */
export const CandidateInviteStatusSchema = z.enum([
  "pending_delivery",
  "active",
  "consented",
  "declined",
  "revoked",
  "expired",
]);

export const ConsentDecisionSchema = z.enum(["consent", "decline"]);
export type ConsentDecision = z.infer<typeof ConsentDecisionSchema>;

/** Versioned notice that must be displayed before assessment content. */
export const ConsentNoticeSchema = z.strictObject({
  version: z.string().min(1),
  purpose: z.string().min(1),
  data_use: z.string().min(1),
  retention: z.string().min(1),
  accommodation_contact_email: z.email(),
  privacy_contact_email: z.email(),
  decline_without_penalty: z.boolean(),
});

/** Exact candidate-safe response from GET/POST /candidate/invites/{token}. */
export const CandidateInviteSchema = z.strictObject({
  invitation_id: z.uuid(),
  organization_name: z.string().min(1),
  role_title: z.string().min(1),
  expires_at: z.string().min(1),
  status: CandidateInviteStatusSchema,
  consent_notice: ConsentNoticeSchema,
  decision: ConsentDecisionSchema.nullable(),
  decision_recorded_at: z.string().min(1).nullable(),
  can_start_assessment: z.boolean(),
  assessment_id: z.uuid().nullish(),
});
export type CandidateInvite = z.infer<typeof CandidateInviteSchema>;

/** Persisted browser envelope for a resumable, contract-valid draft. */
export const CandidateDraftSchema = z.strictObject({
  saved_at: z.string().datetime(),
  response_set: AssessmentResponseSetSchema,
});
export type CandidateDraft = z.infer<typeof CandidateDraftSchema>;

/** Submitted response snapshot and receipt; scores/classifications are excluded. */
export const CandidateCompletionSchema = z.strictObject({
  assessment_id: z.uuid().optional(),
  submitted_at: z.string().datetime(),
  answered_block_count: z.number().int().nonnegative(),
  skipped_block_count: z.number().int().nonnegative(),
  response_set: AssessmentResponseSetSchema,
});
export type CandidateCompletion = z.infer<typeof CandidateCompletionSchema>;

export const SubmissionReceiptSchema = z.strictObject({
  assessment_id: z.uuid(),
});
export type SubmissionReceipt = z.infer<typeof SubmissionReceiptSchema>;
