import { z } from "zod";

import {
  ConfidenceLevelSchema,
  CONSTRUCT_KEYS,
  ConstructKeySchema,
  RatingSchema,
} from "./constructs";

export const RoleConstructRatingSchema = z.strictObject({
  key: ConstructKeySchema,
  rating: RatingSchema,
  confidence: ConfidenceLevelSchema,
  rationale: z.string().trim().min(1),
  evidence: z.array(z.string().trim().min(1)).min(1),
});
export type RoleConstructRating = z.infer<typeof RoleConstructRatingSchema>;

/** Structural LLM output contract. Context-dependent evidence checks are added below. */
export const RoleExtractionSchema = z
  .strictObject({
    constructs: z
      .array(RoleConstructRatingSchema)
      .length(CONSTRUCT_KEYS.length),
    assumptions: z.array(z.string().trim().min(1)),
    needs_human_review: z.literal(true),
  })
  .superRefine((extraction, context) => {
    const observedKeys = new Set(
      extraction.constructs.map((construct) => construct.key),
    );

    for (const key of CONSTRUCT_KEYS) {
      if (!observedKeys.has(key)) {
        context.addIssue({
          code: "custom",
          message: `Missing construct: ${key}`,
          path: ["constructs"],
        });
      }
    }
  });
export type RoleExtraction = z.infer<typeof RoleExtractionSchema>;

/**
 * Bind the structural extraction contract to its submitted job description.
 * Evidence must be a verbatim, case-sensitive substring of that source text.
 */
export function roleExtractionSchemaForJobDescription(jobDescription: string) {
  return RoleExtractionSchema.superRefine((extraction, context) => {
    extraction.constructs.forEach((construct, constructIndex) => {
      construct.evidence.forEach((excerpt, evidenceIndex) => {
        if (!jobDescription.includes(excerpt)) {
          context.addIssue({
            code: "custom",
            message:
              "Evidence must appear verbatim in the submitted job description",
            path: ["constructs", constructIndex, "evidence", evidenceIndex],
          });
        }
      });
    });
  });
}

export function parseRoleExtraction(
  payload: unknown,
  jobDescription: string,
): RoleExtraction {
  if (jobDescription.trim().length === 0) {
    throw new Error(
      "A non-empty job description is required to validate extraction evidence",
    );
  }

  return roleExtractionSchemaForJobDescription(jobDescription).parse(payload);
}
