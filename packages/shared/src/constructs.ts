import { z } from "zod";

/** Version of the serialized domain contracts in this package. */
export const CONTRACT_VERSION = "1.0.0" as const;

/** The six job-related constructs approved for version 1 of the pilot. */
export const CONSTRUCT_KEYS = [
  "autonomy",
  "structure",
  "ambiguity",
  "collaboration",
  "mastery",
  "pace",
] as const;

export const ConstructKeySchema = z.enum(CONSTRUCT_KEYS);
export type ConstructKey = z.infer<typeof ConstructKeySchema>;

export const RatingSchema = z.number().int().min(1).max(5);
export type Rating = z.infer<typeof RatingSchema>;

export const ConfidenceLevelSchema = z.enum(["low", "medium", "high"]);
export type ConfidenceLevel = z.infer<typeof ConfidenceLevelSchema>;

export const AlignmentClassificationSchema = z.enum([
  "aligned",
  "worth_discussing",
  "potential_friction",
  "insufficient_evidence",
]);
export type AlignmentClassification = z.infer<
  typeof AlignmentClassificationSchema
>;

/**
 * Describes how a role rating becomes the target for a candidate comparison.
 * `inverse_role_rating` means the comparison target is `6 - role_rating`.
 */
export const ComparisonTargetSchema = z.enum([
  "role_rating",
  "inverse_role_rating",
]);
export type ComparisonTarget = z.infer<typeof ComparisonTargetSchema>;

export const ConstructDefinitionSchema = z.strictObject({
  key: ConstructKeySchema,
  label: z.string().trim().min(1),
  role_prompt: z.string().trim().min(1),
  candidate_prompt: z.string().trim().min(1),
  comparison_target: ComparisonTargetSchema,
});
export type ConstructDefinition = z.infer<typeof ConstructDefinitionSchema>;

/**
 * Behaviorally worded construct metadata from section 5 of the MVP specification.
 *
 * The structure target follows section 7's explicit inverse formula. Keeping the
 * target in metadata makes this exceptional rule inspectable by later matchers.
 */
export const CONSTRUCT_DEFINITIONS = [
  {
    key: "autonomy",
    label: "Autonomy",
    role_prompt: "How independently the work must be organized",
    candidate_prompt: "How strongly the candidate prefers self-direction",
    comparison_target: "role_rating",
  },
  {
    key: "structure",
    label: "Structure",
    role_prompt: "How defined goals, routines, and requirements are",
    candidate_prompt:
      "How strongly the candidate prefers predictable direction",
    comparison_target: "inverse_role_rating",
  },
  {
    key: "ambiguity",
    label: "Ambiguity tolerance",
    role_prompt: "How often priorities or requirements are unclear or changing",
    candidate_prompt:
      "How comfortable the candidate is acting amid uncertainty",
    comparison_target: "role_rating",
  },
  {
    key: "collaboration",
    label: "Collaboration",
    role_prompt:
      "How much coordination, pairing, and stakeholder work the role needs",
    candidate_prompt: "How much the candidate prefers collaborative work",
    comparison_target: "role_rating",
  },
  {
    key: "mastery",
    label: "Technical mastery",
    role_prompt:
      "How much deep learning and complex problem solving the role offers",
    candidate_prompt:
      "How energizing the candidate finds skill development and hard problems",
    comparison_target: "role_rating",
  },
  {
    key: "pace",
    label: "Pace/context switching",
    role_prompt:
      "How often work requires urgency or shifting between priorities",
    candidate_prompt:
      "How comfortable the candidate is with variety and shifting priorities",
    comparison_target: "role_rating",
  },
] as const satisfies readonly ConstructDefinition[];

/** Construct metadata indexed for deterministic lookups. */
export const CONSTRUCT_DEFINITIONS_BY_KEY: Readonly<
  Record<ConstructKey, ConstructDefinition>
> = Object.fromEntries(
  CONSTRUCT_DEFINITIONS.map((definition) => [definition.key, definition]),
) as Record<ConstructKey, ConstructDefinition>;
