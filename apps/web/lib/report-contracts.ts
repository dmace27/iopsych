import { MatchingResultSchema } from "@iopsych/shared";
import { z } from "zod";

/** Exact 3B envelope, validated before evidence is rendered. */
export const ReportSchema = z.strictObject({
  id: z.uuid(),
  assessment_id: z.uuid(),
  role_profile_id: z.uuid(),
  role_profile_version: z.int().positive(),
  generated_at: z.string().datetime({ offset: true }),
  result: MatchingResultSchema.refine(
    (result) => result.role_profile_approved,
    "Reports require an approved role profile",
  ),
  usage_warning: z.string().min(1),
});
export type Report = z.infer<typeof ReportSchema>;

export const SubmittedAssessmentSchema = z.strictObject({
  assessment_id: z.uuid(),
  invitation_id: z.uuid(),
  candidate_email: z.string().min(1),
  role_profile_id: z.uuid(),
  role_profile_version: z.int().positive(),
  submitted_at: z.string().datetime({ offset: true }).nullable(),
  report_id: z.uuid().nullable(),
});
export type SubmittedAssessment = z.infer<typeof SubmittedAssessmentSchema>;
export const SubmittedAssessmentListSchema = z.array(SubmittedAssessmentSchema);
