import { z } from "zod";

import {
  CONSTRUCT_KEYS,
  ConfidenceLevelSchema,
  ConstructKeySchema,
  RatingSchema,
  type ConfidenceLevel,
  type ConstructKey,
} from "./constructs";
import {
  ContractVersionSchema,
  ScoringConfigSchema,
  type ScoringConfig,
} from "./scoring-config";

export const ASSESSMENT_BLOCK_COUNT = 6;
export const ITEMS_PER_BLOCK = 4;
export const ITEMS_PER_CONSTRUCT = 4;

const DomainIdentifierSchema = z
  .string()
  .trim()
  .min(1)
  .max(100)
  .regex(/^[a-z0-9]+(?:[._-][a-z0-9]+)*$/);

export const AssessmentDefinitionStatusSchema = z.enum([
  "draft",
  "published",
  "retired",
]);
export type AssessmentDefinitionStatus = z.infer<
  typeof AssessmentDefinitionStatusSchema
>;

export const AssessmentItemSchema = z.strictObject({
  id: DomainIdentifierSchema,
  construct_key: ConstructKeySchema,
  statement: z.string().trim().min(1).max(500),
});
export type AssessmentItem = z.infer<typeof AssessmentItemSchema>;

export const AssessmentBlockSchema = z.strictObject({
  id: DomainIdentifierSchema,
  position: z.number().int().min(1).max(ASSESSMENT_BLOCK_COUNT),
  items: z.array(AssessmentItemSchema).length(ITEMS_PER_BLOCK),
});
export type AssessmentBlock = z.infer<typeof AssessmentBlockSchema>;

/**
 * An immutable assessment definition snapshot.
 *
 * Lifecycle status is metadata rather than a scoring gate: historical responses
 * must remain scoreable after their exact definition has been retired.
 */
export const AssessmentDefinitionSchema = z
  .strictObject({
    id: DomainIdentifierSchema,
    version: ContractVersionSchema,
    status: AssessmentDefinitionStatusSchema,
    title: z.string().trim().min(1).max(200),
    blocks: z.array(AssessmentBlockSchema).length(ASSESSMENT_BLOCK_COUNT),
    scoring: ScoringConfigSchema,
  })
  .superRefine((definition, context) => {
    const blockIds = new Set<string>();
    const positions = new Set<number>();
    const itemIds = new Set<string>();
    const exposure = Object.fromEntries(
      CONSTRUCT_KEYS.map((key) => [key, 0]),
    ) as Record<ConstructKey, number>;

    definition.blocks.forEach((block, blockIndex) => {
      if (blockIds.has(block.id)) {
        context.addIssue({
          code: "custom",
          message: "block ids must be unique",
          path: ["blocks", blockIndex, "id"],
        });
      }
      blockIds.add(block.id);

      if (positions.has(block.position)) {
        context.addIssue({
          code: "custom",
          message: "block positions must be unique",
          path: ["blocks", blockIndex, "position"],
        });
      }
      positions.add(block.position);

      const blockConstructs = new Set<ConstructKey>();
      block.items.forEach((item, itemIndex) => {
        if (itemIds.has(item.id)) {
          context.addIssue({
            code: "custom",
            message: "item ids must be unique across the assessment",
            path: ["blocks", blockIndex, "items", itemIndex, "id"],
          });
        }
        itemIds.add(item.id);

        if (blockConstructs.has(item.construct_key)) {
          context.addIssue({
            code: "custom",
            message: "a construct may appear at most once in a block",
            path: ["blocks", blockIndex, "items", itemIndex, "construct_key"],
          });
        }
        blockConstructs.add(item.construct_key);
        exposure[item.construct_key] += 1;
      });
    });

    const expectedPositions = Array.from(
      { length: ASSESSMENT_BLOCK_COUNT },
      (_, index) => index + 1,
    );
    if (expectedPositions.some((position) => !positions.has(position))) {
      context.addIssue({
        code: "custom",
        message: "block positions must contain every position from 1 through 6",
        path: ["blocks"],
      });
    }

    for (const key of CONSTRUCT_KEYS) {
      if (exposure[key] !== ITEMS_PER_CONSTRUCT) {
        context.addIssue({
          code: "custom",
          message: `construct ${key} must appear exactly ${ITEMS_PER_CONSTRUCT} times`,
          path: ["blocks"],
        });
      }
    }

    const orderedThresholds = [...definition.scoring.rating_thresholds].sort(
      (left, right) => left.minimum_raw_score - right.minimum_raw_score,
    );
    if (
      orderedThresholds[0]?.minimum_raw_score !== -ITEMS_PER_CONSTRUCT ||
      orderedThresholds.at(-1)?.maximum_raw_score !== ITEMS_PER_CONSTRUCT
    ) {
      context.addIssue({
        code: "custom",
        message:
          "rating thresholds must cover the complete reachable raw-score range",
        path: ["scoring", "rating_thresholds"],
      });
    }
  });
export type AssessmentDefinition = z.infer<typeof AssessmentDefinitionSchema>;

export const AnsweredBlockResponseSchema = z
  .strictObject({
    block_id: DomainIdentifierSchema,
    skipped: z.literal(false),
    most_like_item_id: DomainIdentifierSchema,
    least_like_item_id: DomainIdentifierSchema,
  })
  .refine(
    (response) => response.most_like_item_id !== response.least_like_item_id,
    {
      message: "most-like and least-like selections must be different items",
      path: ["least_like_item_id"],
    },
  );

export const SkippedBlockResponseSchema = z.strictObject({
  block_id: DomainIdentifierSchema,
  skipped: z.literal(true),
  most_like_item_id: z.null(),
  least_like_item_id: z.null(),
});

export const AssessmentBlockResponseSchema = z.union([
  AnsweredBlockResponseSchema,
  SkippedBlockResponseSchema,
]);
export type AssessmentBlockResponse = z.infer<
  typeof AssessmentBlockResponseSchema
>;

/**
 * Persistable answer snapshot. Omitted blocks represent unsaved/incomplete work;
 * an explicit skipped response represents the candidate's deliberate choice.
 */
export const AssessmentResponseSetSchema = z
  .strictObject({
    assessment_definition_id: DomainIdentifierSchema,
    assessment_definition_version: ContractVersionSchema,
    responses: z
      .array(AssessmentBlockResponseSchema)
      .max(ASSESSMENT_BLOCK_COUNT),
  })
  .superRefine((responseSet, context) => {
    const seenBlocks = new Set<string>();
    responseSet.responses.forEach((response, index) => {
      if (seenBlocks.has(response.block_id)) {
        context.addIssue({
          code: "custom",
          message: "a response set may contain at most one response per block",
          path: ["responses", index, "block_id"],
        });
      }
      seenBlocks.add(response.block_id);
    });
  });
export type AssessmentResponseSet = z.infer<typeof AssessmentResponseSetSchema>;

export const CandidateConstructScoreSchema = z
  .strictObject({
    construct_key: ConstructKeySchema,
    raw_score: z.number().int(),
    rating: RatingSchema,
    confidence: ConfidenceLevelSchema,
    assigned_item_count: z.number().int().nonnegative(),
    answered_item_count: z.number().int().nonnegative(),
    skipped_item_count: z.number().int().nonnegative(),
  })
  .superRefine((score, context) => {
    if (
      score.assigned_item_count !==
      score.answered_item_count + score.skipped_item_count
    ) {
      context.addIssue({
        code: "custom",
        message: "assigned item count must equal answered plus skipped items",
        path: ["assigned_item_count"],
      });
    }
    if (score.assigned_item_count !== ITEMS_PER_CONSTRUCT) {
      context.addIssue({
        code: "custom",
        message: `each construct score must account for ${ITEMS_PER_CONSTRUCT} assigned items`,
        path: ["assigned_item_count"],
      });
    }
    if (Math.abs(score.raw_score) > score.answered_item_count) {
      context.addIssue({
        code: "custom",
        message: "raw score cannot exceed the number of answered items",
        path: ["raw_score"],
      });
    }
  });
export type CandidateConstructScore = z.infer<
  typeof CandidateConstructScoreSchema
>;

export const AssessmentScoreResultSchema = z
  .strictObject({
    assessment_definition_id: DomainIdentifierSchema,
    assessment_definition_version: ContractVersionSchema,
    scoring_version: ContractVersionSchema,
    construct_scores: z
      .array(CandidateConstructScoreSchema)
      .length(CONSTRUCT_KEYS.length),
  })
  .superRefine((result, context) => {
    const scoreKeys = result.construct_scores.map(
      ({ construct_key }) => construct_key,
    );
    for (const key of CONSTRUCT_KEYS) {
      if (scoreKeys.filter((scoreKey) => scoreKey === key).length !== 1) {
        context.addIssue({
          code: "custom",
          message: "construct scores must contain every construct exactly once",
          path: ["construct_scores"],
        });
        break;
      }
    }
  });
export type AssessmentScoreResult = z.infer<typeof AssessmentScoreResultSchema>;

export type AssessmentScoringErrorCode =
  | "definition_mismatch"
  | "incomplete_assessment"
  | "unknown_block"
  | "invalid_item_selection"
  | "unmapped_raw_score"
  | "unmapped_confidence";

/** A stable domain error for invalid definition/response combinations. */
export class AssessmentScoringError extends Error {
  readonly code: AssessmentScoringErrorCode;

  constructor(code: AssessmentScoringErrorCode, message: string) {
    super(message);
    this.name = "AssessmentScoringError";
    this.code = code;
  }
}

function confidenceForSkippedItems(
  skippedItems: number,
  config: ScoringConfig,
): ConfidenceLevel {
  for (const rule of [
    config.candidate_confidence.high,
    config.candidate_confidence.medium,
    config.candidate_confidence.low,
  ]) {
    const withinMaximum =
      rule.maximum_skipped_items === null ||
      skippedItems <= rule.maximum_skipped_items;
    if (skippedItems >= rule.minimum_skipped_items && withinMaximum) {
      return rule.level;
    }
  }

  // ScoringConfigSchema makes the configured ranges exhaustive.
  throw new AssessmentScoringError(
    "unmapped_confidence",
    `No confidence rule contains ${skippedItems} skipped items`,
  );
}

function ratingForRawScore(rawScore: number, config: ScoringConfig) {
  const threshold = config.rating_thresholds.find(
    ({ minimum_raw_score, maximum_raw_score }) =>
      rawScore >= minimum_raw_score && rawScore <= maximum_raw_score,
  );
  if (threshold === undefined) {
    throw new AssessmentScoringError(
      "unmapped_raw_score",
      `No rating threshold contains raw score ${rawScore}`,
    );
  }
  return threshold.rating;
}

/**
 * Score a complete forced-choice response set without I/O or mutable state.
 *
 * Statement display order is irrelevant: selections are resolved by stable item
 * ids from the versioned definition. The result carries both versions required
 * to persist and faithfully interpret a historical score.
 */
export function scoreAssessment(
  definitionInput: AssessmentDefinition,
  responseSetInput: AssessmentResponseSet,
): AssessmentScoreResult {
  const definition = AssessmentDefinitionSchema.parse(definitionInput);
  const responseSet = AssessmentResponseSetSchema.parse(responseSetInput);

  if (
    responseSet.assessment_definition_id !== definition.id ||
    responseSet.assessment_definition_version !== definition.version
  ) {
    throw new AssessmentScoringError(
      "definition_mismatch",
      "Response set does not reference the supplied assessment definition version",
    );
  }

  const responseByBlock = new Map(
    responseSet.responses.map((response) => [response.block_id, response]),
  );
  for (const response of responseSet.responses) {
    if (!definition.blocks.some((block) => block.id === response.block_id)) {
      throw new AssessmentScoringError(
        "unknown_block",
        `Response references unknown block ${response.block_id}`,
      );
    }
  }
  if (responseByBlock.size !== definition.blocks.length) {
    throw new AssessmentScoringError(
      "incomplete_assessment",
      "Every assessment block must be answered or explicitly skipped before scoring",
    );
  }

  const accumulators = Object.fromEntries(
    CONSTRUCT_KEYS.map((key) => [
      key,
      { rawScore: 0, answeredItems: 0, skippedItems: 0 },
    ]),
  ) as Record<
    ConstructKey,
    { rawScore: number; answeredItems: number; skippedItems: number }
  >;

  for (const block of definition.blocks) {
    const response = responseByBlock.get(block.id);
    if (response === undefined) {
      // The completeness check above guarantees this branch is unreachable.
      throw new AssessmentScoringError(
        "incomplete_assessment",
        `Missing response for block ${block.id}`,
      );
    }

    if (response.skipped) {
      for (const item of block.items) {
        accumulators[item.construct_key].skippedItems += 1;
      }
      continue;
    }

    const itemsById = new Map(block.items.map((item) => [item.id, item]));
    const mostLike = itemsById.get(response.most_like_item_id);
    const leastLike = itemsById.get(response.least_like_item_id);
    if (mostLike === undefined || leastLike === undefined) {
      throw new AssessmentScoringError(
        "invalid_item_selection",
        `Selections for block ${block.id} must reference items in that block`,
      );
    }

    for (const item of block.items) {
      accumulators[item.construct_key].answeredItems += 1;
    }
    accumulators[mostLike.construct_key].rawScore +=
      definition.scoring.choice_weights.most_like;
    accumulators[leastLike.construct_key].rawScore +=
      definition.scoring.choice_weights.least_like;
  }

  const constructScores = CONSTRUCT_KEYS.map((constructKey) => {
    const accumulator = accumulators[constructKey];
    return {
      construct_key: constructKey,
      raw_score: accumulator.rawScore,
      rating: ratingForRawScore(accumulator.rawScore, definition.scoring),
      confidence: confidenceForSkippedItems(
        accumulator.skippedItems,
        definition.scoring,
      ),
      assigned_item_count: accumulator.answeredItems + accumulator.skippedItems,
      answered_item_count: accumulator.answeredItems,
      skipped_item_count: accumulator.skippedItems,
    };
  });

  return AssessmentScoreResultSchema.parse({
    assessment_definition_id: definition.id,
    assessment_definition_version: definition.version,
    scoring_version: definition.scoring.version,
    construct_scores: constructScores,
  });
}
