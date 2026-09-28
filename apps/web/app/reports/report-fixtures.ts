import { CONSTRUCT_KEYS, matchRoleProfile } from "@iopsych/shared";
import type { Report, SubmittedAssessment } from "../../lib/report-contracts";

/** Synthetic data used exclusively by report UI and adapter tests. */
export const reportFixture: Report = {
  id: "11111111-1111-4111-8111-111111111111",
  assessment_id: "22222222-2222-4222-8222-222222222222",
  role_profile_id: "33333333-3333-4333-8333-333333333333",
  role_profile_version: 2,
  generated_at: "2026-09-27T12:00:00Z",
  usage_warning:
    "Interview preparation only. Never rank candidates or make an employment decision using this report.",
  result: matchRoleProfile(
    {
      approved: true,
      constructs: CONSTRUCT_KEYS.map((key) => ({
        key,
        rating: 4,
        confidence: key === "autonomy" ? "low" : "high",
        rationale: `Reviewed ${key} rationale`,
        evidence: [`Exact ${key} job evidence`],
      })),
    },
    {
      assessment_definition_id: "synthetic-assessment",
      assessment_definition_version: "1.0.0",
      scoring_version: "1.0.0",
      construct_scores: CONSTRUCT_KEYS.map((key) => ({
        construct_key: key,
        rating: key === "pace" ? 1 : key === "mastery" ? 2 : 3,
        confidence: "high",
        raw_score: 0,
        assigned_item_count: 4,
        answered_item_count: 4,
        skipped_item_count: 0,
      })),
    },
  ),
};
export const sourceFixture: SubmittedAssessment = {
  assessment_id: reportFixture.assessment_id,
  invitation_id: "44444444-4444-4444-8444-444444444444",
  candidate_email: "synthetic@example.test",
  role_profile_id: reportFixture.role_profile_id,
  role_profile_version: 2,
  submitted_at: reportFixture.generated_at,
  report_id: null,
};
