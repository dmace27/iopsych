import {
  AssessmentDefinitionSchema,
  AssessmentResponseSetSchema,
} from "@iopsych/shared";
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

/** The retained v1 renderer; new semantic versions require an explicit reader. */
export const CandidateAssignmentSchema = z.strictObject({
  assessment_definition_id: z.literal("work-preferences-pilot"),
  assessment_definition_version: z.literal("1.0.0"),
  scoring_version: z.literal("1.0.0"),
  matching_algorithm_version: z.literal("1.0.0"),
  definition_sha256: z.string().regex(/^[a-f0-9]{64}$/),
});
export type CandidateAssignment = z.infer<typeof CandidateAssignmentSchema>;
export const CandidateDefinitionSchema = z
  .strictObject({
    assignment: CandidateAssignmentSchema,
    definition: AssessmentDefinitionSchema,
  })
  .refine(
    ({ assignment, definition }) =>
      assignment.assessment_definition_id === definition.id &&
      assignment.assessment_definition_version === definition.version &&
      assignment.scoring_version === definition.scoring.version,
    "The assigned definition does not match its metadata.",
  );
export type CandidateDefinition = z.infer<typeof CandidateDefinitionSchema>;

/** Frozen backend legacy-v1 checksum, not the current bundled definition. */
export const LEGACY_V1_DEFINITION_SHA256 =
  "021233ca4dab9c86b87aeabca88f503bf7c70fd0b0d324c64e788b620aeb6e3c";

/** Persisted browser envelope for a resumable, contract-valid draft. */
export const CandidateDraftSchema = z.strictObject({
  definition_sha256: z
    .string()
    .regex(/^[a-f0-9]{64}$/)
    .optional(),
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
