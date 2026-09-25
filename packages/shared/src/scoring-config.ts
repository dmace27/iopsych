import { z } from "zod";

import { ConfidenceLevelSchema, RatingSchema } from "./constructs";

export const ContractVersionSchema = z.string().regex(/^\d+\.\d+\.\d+$/);

export const RawScoreThresholdSchema = z
  .strictObject({
    rating: RatingSchema,
    minimum_raw_score: z.number().int(),
    maximum_raw_score: z.number().int(),
  })
  .refine(
    (threshold) => threshold.minimum_raw_score <= threshold.maximum_raw_score,
    {
      message: "minimum_raw_score must not exceed maximum_raw_score",
    },
  );
export type RawScoreThreshold = z.infer<typeof RawScoreThresholdSchema>;

export const CandidateConfidenceRulesSchema = z.strictObject({
  high: z.strictObject({
    level: z.literal(ConfidenceLevelSchema.enum.high),
    minimum_skipped_items: z.literal(0),
    maximum_skipped_items: z.literal(0),
  }),
  medium: z.strictObject({
    level: z.literal(ConfidenceLevelSchema.enum.medium),
    minimum_skipped_items: z.literal(1),
    maximum_skipped_items: z.literal(1),
  }),
  low: z.strictObject({
    level: z.literal(ConfidenceLevelSchema.enum.low),
    minimum_skipped_items: z.literal(2),
    maximum_skipped_items: z.null(),
  }),
});

/**
 * Versioned forced-choice scoring configuration.
 *
 * Threshold values are intentionally data, not hard-coded policy. Package 2A must
 * supply reviewed thresholds for a specific assessment definition.
 */
export const ScoringConfigSchema = z
  .strictObject({
    version: ContractVersionSchema,
    choice_weights: z.strictObject({
      most_like: z.literal(1),
      least_like: z.literal(-1),
    }),
    rating_thresholds: z.array(RawScoreThresholdSchema).length(5),
    candidate_confidence: CandidateConfidenceRulesSchema,
  })
  .superRefine((config, context) => {
    const orderedThresholds = [...config.rating_thresholds].sort(
      (left, right) => left.rating - right.rating,
    );

    orderedThresholds.forEach((threshold, index) => {
      const expectedRating = index + 1;
      if (threshold.rating !== expectedRating) {
        context.addIssue({
          code: "custom",
          message:
            "rating_thresholds must define each rating from 1 through 5 exactly once",
          path: ["rating_thresholds"],
        });
      }

      const previousThreshold = orderedThresholds[index - 1];
      if (
        previousThreshold !== undefined &&
        threshold.minimum_raw_score !== previousThreshold.maximum_raw_score + 1
      ) {
        context.addIssue({
          code: "custom",
          message: "rating_thresholds must be contiguous and non-overlapping",
          path: ["rating_thresholds"],
        });
      }
    });
  });
export type ScoringConfig = z.infer<typeof ScoringConfigSchema>;
