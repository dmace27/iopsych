import { z } from "zod";

import {
  ITEMS_PER_CONSTRUCT,
  AssessmentScoreResultSchema,
  type AssessmentScoreResult,
  type CandidateConstructScore,
} from "./assessment";
import {
  AlignmentClassificationSchema,
  CONSTRUCT_DEFINITIONS_BY_KEY,
  CONSTRUCT_KEYS,
  ConfidenceLevelSchema,
  ConstructKeySchema,
  RatingSchema,
  type AlignmentClassification,
  type ConfidenceLevel,
  type ConstructKey,
} from "./constructs";
import {
  RoleConstructRatingSchema,
  type RoleConstructRating,
} from "./role-extraction";
import { ContractVersionSchema } from "./scoring-config";

/** Version of the deterministic rules and question-selection behavior. */
export const MATCHING_ALGORITHM_VERSION = "1.0.0" as const;

export const MatchingRuleSchema = z.enum([
  "role_profile_not_approved",
  "low_confidence",
  "difference_at_most_one",
  "difference_equals_two",
  "difference_at_least_three",
]);
export type MatchingRule = z.infer<typeof MatchingRuleSchema>;

export type MatchingErrorCode = "construct_mismatch" | "question_not_found";

/** Stable domain error for otherwise-valid snapshots that cannot be compared. */
export class MatchingError extends Error {
  readonly code: MatchingErrorCode;

  constructor(code: MatchingErrorCode, message: string) {
    super(message);
    this.name = "MatchingError";
    this.code = code;
  }
}

function requireEveryConstruct(
  values: ReadonlyArray<{ key: ConstructKey }>,
  context: z.RefinementCtx,
) {
  const keys = values.map(({ key }) => key);
  if (
    new Set(keys).size !== CONSTRUCT_KEYS.length ||
    CONSTRUCT_KEYS.some((key) => !keys.includes(key))
  ) {
    context.addIssue({
      code: "custom",
      message: "constructs must contain each version 1 construct exactly once",
      path: ["constructs"],
    });
  }
}

export const MatchingRoleProfileSchema = z
  .strictObject({
    approved: z.boolean(),
    constructs: z
      .array(RoleConstructRatingSchema)
      .length(CONSTRUCT_KEYS.length),
  })
  .superRefine((profile, context) =>
    requireEveryConstruct(profile.constructs, context),
  );
export type MatchingRoleProfile = z.infer<typeof MatchingRoleProfileSchema>;

const QuestionIdentifierSchema = z
  .string()
  .trim()
  .min(1)
  .max(160)
  .regex(/^[a-z0-9]+(?:[._-][a-z0-9]+)*$/);

export const InterviewQuestionSchema = z.strictObject({
  id: QuestionIdentifierSchema,
  text: z.string().trim().min(1),
});
export type InterviewQuestion = z.infer<typeof InterviewQuestionSchema>;

export const InterviewQuestionPairSchema = z.strictObject({
  primary: InterviewQuestionSchema,
  follow_up: InterviewQuestionSchema,
});
export type InterviewQuestionPair = z.infer<typeof InterviewQuestionPairSchema>;

export const InterviewQuestionLibraryEntrySchema = z.strictObject({
  construct_key: ConstructKeySchema,
  classification: AlignmentClassificationSchema,
  review_status: z.literal("approved"),
  questions: InterviewQuestionPairSchema,
});
export type InterviewQuestionLibraryEntry = z.infer<
  typeof InterviewQuestionLibraryEntrySchema
>;

/** A complete reviewed library with one unique pair for every engine outcome. */
export const InterviewQuestionLibrarySchema = z
  .array(InterviewQuestionLibraryEntrySchema)
  .length(CONSTRUCT_KEYS.length * AlignmentClassificationSchema.options.length)
  .superRefine((entries, context) => {
    const keys = new Set<string>();
    const questionIds = new Set<string>();
    entries.forEach((entry, index) => {
      const key = `${entry.construct_key}/${entry.classification}`;
      if (keys.has(key)) {
        context.addIssue({
          code: "custom",
          message: "question library keys must be unique",
          path: [index],
        });
      }
      keys.add(key);

      for (const question of [
        entry.questions.primary,
        entry.questions.follow_up,
      ]) {
        if (questionIds.has(question.id)) {
          context.addIssue({
            code: "custom",
            message: "question ids must be unique",
            path: [index, "questions"],
          });
        }
        questionIds.add(question.id);
      }
    });

    for (const constructKey of CONSTRUCT_KEYS) {
      for (const classification of AlignmentClassificationSchema.options) {
        if (!keys.has(`${constructKey}/${classification}`)) {
          context.addIssue({
            code: "custom",
            message: `missing question library key ${constructKey}/${classification}`,
          });
        }
      }
    }
  });
export type InterviewQuestionLibrary = z.infer<
  typeof InterviewQuestionLibrarySchema
>;

export const CandidateResponseSummarySchema = z
  .strictObject({
    rating: RatingSchema,
    confidence: ConfidenceLevelSchema,
    raw_score: z.number().int(),
    assigned_item_count: z.number().int().nonnegative(),
    answered_item_count: z.number().int().nonnegative(),
    skipped_item_count: z.number().int().nonnegative(),
  })
  .superRefine((summary, context) => {
    if (
      summary.assigned_item_count !==
      summary.answered_item_count + summary.skipped_item_count
    ) {
      context.addIssue({
        code: "custom",
        message: "assigned item count must equal answered plus skipped items",
        path: ["assigned_item_count"],
      });
    }
    if (summary.assigned_item_count !== ITEMS_PER_CONSTRUCT) {
      context.addIssue({
        code: "custom",
        message: `each construct summary must account for ${ITEMS_PER_CONSTRUCT} assigned items`,
        path: ["assigned_item_count"],
      });
    }
    if (Math.abs(summary.raw_score) > summary.answered_item_count) {
      context.addIssue({
        code: "custom",
        message: "raw score cannot exceed the number of answered items",
        path: ["raw_score"],
      });
    }
  });
export type CandidateResponseSummary = z.infer<
  typeof CandidateResponseSummarySchema
>;

export const RoleEvidenceSummarySchema = z
  .strictObject({
    rating: RatingSchema,
    confidence: ConfidenceLevelSchema,
    rationale: z.string().trim().min(1),
    evidence: z.array(z.string().trim().min(1)).min(1),
    comparison_target: z.enum(["role_rating", "inverse_role_rating"]),
    comparison_rating: RatingSchema,
  })
  .superRefine((summary, context) => {
    const expected =
      summary.comparison_target === "inverse_role_rating"
        ? 6 - summary.rating
        : summary.rating;
    if (summary.comparison_rating !== expected) {
      context.addIssue({
        code: "custom",
        message: "comparison rating must match the declared comparison target",
        path: ["comparison_rating"],
      });
    }
  });
export type RoleEvidenceSummary = z.infer<typeof RoleEvidenceSummarySchema>;

export const RuleExplanationSchema = z.strictObject({
  rule: MatchingRuleSchema,
  absolute_difference: z.number().int().min(0).max(4),
  description: z.string().trim().min(1),
});
export type RuleExplanation = z.infer<typeof RuleExplanationSchema>;

export const AlignmentExplanationSchema = z.strictObject({
  role: RoleEvidenceSummarySchema,
  candidate_response: CandidateResponseSummarySchema,
  applied_rule: RuleExplanationSchema,
  uncertainty: z.string().trim().min(1).nullable(),
});
export type AlignmentExplanation = z.infer<typeof AlignmentExplanationSchema>;

export const AlignmentItemSchema = z.strictObject({
  construct_key: ConstructKeySchema,
  classification: AlignmentClassificationSchema,
  confidence: ConfidenceLevelSchema,
  explanation: AlignmentExplanationSchema,
  interview_questions: InterviewQuestionPairSchema,
});
export type AlignmentItem = z.infer<typeof AlignmentItemSchema>;

export const MatchingResultSchema = z
  .strictObject({
    algorithm_version: z.literal(MATCHING_ALGORITHM_VERSION),
    role_profile_approved: z.boolean(),
    assessment_definition_id: z.string().trim().min(1),
    assessment_definition_version: ContractVersionSchema,
    scoring_version: ContractVersionSchema,
    items: z.array(AlignmentItemSchema).length(CONSTRUCT_KEYS.length),
  })
  .superRefine((result, context) => {
    requireEveryConstruct(
      result.items.map((item) => ({ key: item.construct_key })),
      context,
    );
  });
export type MatchingResult = z.infer<typeof MatchingResultSchema>;

function question(
  constructKey: ConstructKey,
  classification: AlignmentClassification,
  primary: string,
  followUp: string,
): InterviewQuestionLibraryEntry {
  const prefix = `${constructKey}.${classification}`;
  return {
    construct_key: constructKey,
    classification,
    review_status: "approved",
    questions: {
      primary: { id: `${prefix}.primary.v1`, text: primary },
      follow_up: { id: `${prefix}.follow-up.v1`, text: followUp },
    },
  };
}

/**
 * Reviewed version 1 question content. Every construct/classification pair is
 * explicit so the critical path never generates or silently substitutes text.
 */
export const APPROVED_INTERVIEW_QUESTION_LIBRARY_V1 =
  InterviewQuestionLibrarySchema.parse([
    question(
      "autonomy",
      "aligned",
      "Tell me about a role where the level of day-to-day ownership worked well for you.",
      "What decisions did you make independently, and when did you seek direction?",
    ),
    question(
      "autonomy",
      "worth_discussing",
      "Tell me about a time the amount of direction you received differed from what you preferred.",
      "How did you clarify decision boundaries and stay effective?",
    ),
    question(
      "autonomy",
      "potential_friction",
      "Describe a project where you had to work with substantially more or less autonomy than usual.",
      "What support or working agreement helped you deliver effectively?",
    ),
    question(
      "autonomy",
      "insufficient_evidence",
      "Tell me how you prefer decisions and ownership to be divided in your day-to-day work.",
      "Can you share a recent example of that arrangement working well?",
    ),
    question(
      "structure",
      "aligned",
      "Tell me about a role where the level of process and clarity supported your best work.",
      "Which routines or expectations were most useful?",
    ),
    question(
      "structure",
      "worth_discussing",
      "Describe a time the available process or direction differed from what you preferred.",
      "How did you create enough clarity to move forward?",
    ),
    question(
      "structure",
      "potential_friction",
      "Tell me about a time you worked with much more or less structure than you normally prefer.",
      "What support, information, or routines helped you work effectively?",
    ),
    question(
      "structure",
      "insufficient_evidence",
      "Tell me what kinds of goals, routines, and direction help you work effectively.",
      "How do you respond when those conditions are not available?",
    ),
    question(
      "ambiguity",
      "aligned",
      "Tell me about a time you worked effectively while requirements were incomplete or changing.",
      "How did you decide what to clarify and what to act on?",
    ),
    question(
      "ambiguity",
      "worth_discussing",
      "Describe a project where uncertainty affected how you planned your work.",
      "What information or checkpoints helped you maintain progress?",
    ),
    question(
      "ambiguity",
      "potential_friction",
      "Tell me about a time requirements were incomplete or changed quickly. How did you decide what to do next?",
      "What support, information, or routines helped you work effectively?",
    ),
    question(
      "ambiguity",
      "insufficient_evidence",
      "Tell me how you approach work when important details are not yet known.",
      "Can you share an example and the outcome?",
    ),
    question(
      "collaboration",
      "aligned",
      "Tell me about a team interaction pattern that helped you do strong work.",
      "How did you contribute while preserving time for individual work?",
    ),
    question(
      "collaboration",
      "worth_discussing",
      "Describe a time a role required more or less coordination than you expected.",
      "How did you adapt your communication and working habits?",
    ),
    question(
      "collaboration",
      "potential_friction",
      "Tell me about a project whose collaboration demands differed greatly from your preference.",
      "What agreements or boundaries helped the team and your own work?",
    ),
    question(
      "collaboration",
      "insufficient_evidence",
      "Tell me how you prefer to balance independent work with coordination and discussion.",
      "What recent example best illustrates that preference?",
    ),
    question(
      "mastery",
      "aligned",
      "Tell me about a technically difficult problem that kept you engaged.",
      "How did you deepen your knowledge while delivering the work?",
    ),
    question(
      "mastery",
      "worth_discussing",
      "Describe a time a role offered a different level of technical challenge than you expected.",
      "How did you find or create useful learning opportunities?",
    ),
    question(
      "mastery",
      "potential_friction",
      "Tell me about a period when the depth of technical learning available differed greatly from what motivated you.",
      "What made the work sustainable or helped you remain effective?",
    ),
    question(
      "mastery",
      "insufficient_evidence",
      "Tell me what kinds of learning and problem-solving opportunities are most engaging for you.",
      "Can you share a recent example?",
    ),
    question(
      "pace",
      "aligned",
      "Tell me about a work pace and mix of priorities that helped you be effective.",
      "How did you protect quality while maintaining momentum?",
    ),
    question(
      "pace",
      "worth_discussing",
      "Describe a time the pace or amount of context switching differed from what you expected.",
      "How did you organize the work and communicate tradeoffs?",
    ),
    question(
      "pace",
      "potential_friction",
      "Tell me about a role with substantially more or less urgency and context switching than you preferred.",
      "What boundaries or practices helped you remain effective?",
    ),
    question(
      "pace",
      "insufficient_evidence",
      "Tell me what pace and balance between focus and shifting priorities supports your best work.",
      "How have you handled a different pace when the role required it?",
    ),
  ]);

const questionsByKey = new Map(
  APPROVED_INTERVIEW_QUESTION_LIBRARY_V1.map((entry) => [
    `${entry.construct_key}/${entry.classification}`,
    entry,
  ]),
);

const confidenceOrder: Readonly<Record<ConfidenceLevel, number>> = {
  low: 0,
  medium: 1,
  high: 2,
};

/** Return the inspectable role target, applying structure's inverse rule. */
export function comparisonRating(
  constructKey: ConstructKey,
  roleRating: number,
): number {
  return CONSTRUCT_DEFINITIONS_BY_KEY[constructKey].comparison_target ===
    "inverse_role_rating"
    ? 6 - roleRating
    : roleRating;
}

/** Return the lower evidence confidence using the documented ordinal scale. */
export function lowerConfidence(
  roleConfidence: ConfidenceLevel,
  candidateConfidence: ConfidenceLevel,
): ConfidenceLevel {
  return confidenceOrder[roleConfidence] <= confidenceOrder[candidateConfidence]
    ? roleConfidence
    : candidateConfidence;
}

type ClassificationResult = Readonly<{
  classification: AlignmentClassification;
  rule: MatchingRule;
  description: string;
  uncertainty: string | null;
}>;

function classify(
  approved: boolean,
  confidence: ConfidenceLevel,
  difference: number,
): ClassificationResult {
  if (!approved) {
    return {
      classification: "insufficient_evidence",
      rule: "role_profile_not_approved",
      description:
        "The role profile is not approved, so no alignment or friction label is produced.",
      uncertainty: "Role ratings require human approval before interpretation.",
    };
  }
  if (confidence === "low") {
    return {
      classification: "insufficient_evidence",
      rule: "low_confidence",
      description:
        "At least one evidence source has low confidence, so no alignment or friction label is produced.",
      uncertainty: "The lower of role and candidate confidence is low.",
    };
  }
  if (difference <= 1) {
    return {
      classification: "aligned",
      rule: "difference_at_most_one",
      description: "The absolute rating difference is at most 1.",
      uncertainty: null,
    };
  }
  if (difference === 2) {
    return {
      classification: "worth_discussing",
      rule: "difference_equals_two",
      description: "The absolute rating difference is exactly 2.",
      uncertainty: null,
    };
  }
  return {
    classification: "potential_friction",
    rule: "difference_at_least_three",
    description: "The absolute rating difference is at least 3.",
    uncertainty: null,
  };
}

function selectQuestions(
  constructKey: ConstructKey,
  classification: AlignmentClassification,
): InterviewQuestionPair {
  const entry = questionsByKey.get(`${constructKey}/${classification}`);
  if (entry === undefined) {
    throw new MatchingError(
      "question_not_found",
      `No approved questions exist for ${constructKey}/${classification}`,
    );
  }
  return entry.questions;
}

/** Compare one construct without I/O, randomness, mutation, or hidden weighting. */
export function matchConstruct(
  role: RoleConstructRating,
  candidate: CandidateConstructScore,
  roleProfileApproved: boolean,
): AlignmentItem {
  if (role.key !== candidate.construct_key) {
    throw new MatchingError(
      "construct_mismatch",
      `Role construct ${role.key} cannot be compared with candidate construct ${candidate.construct_key}`,
    );
  }

  const definition = CONSTRUCT_DEFINITIONS_BY_KEY[role.key];
  const targetRating = comparisonRating(role.key, role.rating);
  const difference = Math.abs(targetRating - candidate.rating);
  const confidence = lowerConfidence(role.confidence, candidate.confidence);
  const outcome = classify(roleProfileApproved, confidence, difference);

  return {
    construct_key: role.key,
    classification: outcome.classification,
    confidence,
    explanation: {
      role: {
        rating: role.rating,
        confidence: role.confidence,
        rationale: role.rationale,
        evidence: [...role.evidence],
        comparison_target: definition.comparison_target,
        comparison_rating: targetRating,
      },
      candidate_response: {
        rating: candidate.rating,
        confidence: candidate.confidence,
        raw_score: candidate.raw_score,
        assigned_item_count: candidate.assigned_item_count,
        answered_item_count: candidate.answered_item_count,
        skipped_item_count: candidate.skipped_item_count,
      },
      applied_rule: {
        rule: outcome.rule,
        absolute_difference: difference,
        description: outcome.description,
      },
      uncertainty: outcome.uncertainty,
    },
    interview_questions: selectQuestions(role.key, outcome.classification),
  };
}

/** Compare all six constructs in canonical order and retain input versions. */
export function matchRoleProfile(
  roleProfile: MatchingRoleProfile,
  candidateScores: AssessmentScoreResult,
): MatchingResult {
  const parsedRoleProfile = MatchingRoleProfileSchema.parse(roleProfile);
  const parsedCandidateScores =
    AssessmentScoreResultSchema.parse(candidateScores);
  const rolesByKey = new Map(
    parsedRoleProfile.constructs.map((construct) => [construct.key, construct]),
  );
  const candidatesByKey = new Map(
    parsedCandidateScores.construct_scores.map((score) => [
      score.construct_key,
      score,
    ]),
  );
  const items = CONSTRUCT_KEYS.map((key) =>
    matchConstruct(
      rolesByKey.get(key)!,
      candidatesByKey.get(key)!,
      parsedRoleProfile.approved,
    ),
  );

  return MatchingResultSchema.parse({
    algorithm_version: MATCHING_ALGORITHM_VERSION,
    role_profile_approved: parsedRoleProfile.approved,
    assessment_definition_id: parsedCandidateScores.assessment_definition_id,
    assessment_definition_version:
      parsedCandidateScores.assessment_definition_version,
    scoring_version: parsedCandidateScores.scoring_version,
    items,
  });
}
