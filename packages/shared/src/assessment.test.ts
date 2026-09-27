import { readFile } from "node:fs/promises";
import path from "node:path";

import { describe, expect, it } from "vitest";

import {
  AssessmentDefinitionSchema,
  AssessmentResponseSetSchema,
  AssessmentScoreResultSchema,
  AssessmentScoringError,
  CONSTRUCT_KEYS,
  PILOT_ASSESSMENT_DEFINITION_V1,
  scoreAssessment,
  type AssessmentBlock,
  type AssessmentBlockResponse,
  type AssessmentDefinition,
  type AssessmentResponseSet,
  type ConstructKey,
} from "./index";

function answeredResponse(
  block: AssessmentBlock,
  mostLikeIndex = 0,
  leastLikeIndex = 1,
): AssessmentBlockResponse {
  return {
    block_id: block.id,
    skipped: false,
    most_like_item_id: block.items[mostLikeIndex].id,
    least_like_item_id: block.items[leastLikeIndex].id,
  };
}

function completeResponseSet(
  definition: AssessmentDefinition = PILOT_ASSESSMENT_DEFINITION_V1,
): AssessmentResponseSet {
  return {
    assessment_definition_id: definition.id,
    assessment_definition_version: definition.version,
    responses: definition.blocks.map((block) => answeredResponse(block)),
  };
}

function responsesForRawScore(
  constructKey: ConstructKey,
  desiredRawScore: number,
): AssessmentResponseSet {
  let targetSelectionsRemaining = Math.abs(desiredRawScore);
  const responses = PILOT_ASSESSMENT_DEFINITION_V1.blocks.map((block) => {
    const targetIndex = block.items.findIndex(
      (item) => item.construct_key === constructKey,
    );
    const otherIndexes = block.items
      .map((_, index) => index)
      .filter((index) => index !== targetIndex);

    if (targetIndex === -1 || targetSelectionsRemaining === 0) {
      return answeredResponse(block, otherIndexes[0], otherIndexes[1]);
    }

    targetSelectionsRemaining -= 1;
    return desiredRawScore > 0
      ? answeredResponse(block, targetIndex, otherIndexes[0])
      : answeredResponse(block, otherIndexes[0], targetIndex);
  });

  return {
    assessment_definition_id: PILOT_ASSESSMENT_DEFINITION_V1.id,
    assessment_definition_version: PILOT_ASSESSMENT_DEFINITION_V1.version,
    responses,
  };
}

function scoreFor(
  constructKey: ConstructKey,
  responseSet: AssessmentResponseSet,
) {
  const result = scoreAssessment(PILOT_ASSESSMENT_DEFINITION_V1, responseSet);
  return result.construct_scores.find(
    (score) => score.construct_key === constructKey,
  )!;
}

describe("versioned assessment definition", () => {
  it("matches the checked-in language-neutral pilot definition", async () => {
    const contents = await readFile(
      path.resolve(
        import.meta.dirname,
        "..",
        "definitions",
        "v1",
        "pilot-assessment.json",
      ),
      "utf8",
    );

    expect(JSON.parse(contents)).toEqual(PILOT_ASSESSMENT_DEFINITION_V1);
  });

  it("contains six four-item blocks with balanced construct exposure", () => {
    const definition = AssessmentDefinitionSchema.parse(
      PILOT_ASSESSMENT_DEFINITION_V1,
    );
    const exposure = Object.fromEntries(
      CONSTRUCT_KEYS.map((key) => [key, 0]),
    ) as Record<ConstructKey, number>;

    expect(definition.status).toBe("draft");
    expect(definition.blocks).toHaveLength(6);
    for (const block of definition.blocks) {
      expect(block.items).toHaveLength(4);
      expect(new Set(block.items.map((item) => item.construct_key)).size).toBe(
        4,
      );
      for (const item of block.items) {
        exposure[item.construct_key] += 1;
      }
    }
    expect(exposure).toEqual(
      Object.fromEntries(CONSTRUCT_KEYS.map((key) => [key, 4])),
    );
  });

  const invalidDefinitionCases: ReadonlyArray<
    readonly [string, (definition: AssessmentDefinition) => void]
  > = [
    [
      "duplicate block id",
      (definition) => {
        definition.blocks[1].id = definition.blocks[0].id;
      },
    ],
    [
      "duplicate position",
      (definition) => {
        definition.blocks[1].position = definition.blocks[0].position;
      },
    ],
    [
      "duplicate item id",
      (definition) => {
        definition.blocks[1].items[0].id = definition.blocks[0].items[0].id;
      },
    ],
    [
      "duplicate construct in a block",
      (definition) => {
        definition.blocks[0].items[1].construct_key =
          definition.blocks[0].items[0].construct_key;
      },
    ],
    [
      "incomplete score range",
      (definition) => {
        definition.scoring.rating_thresholds[0].minimum_raw_score = -5;
      },
    ],
  ];

  it.each(invalidDefinitionCases)(
    "rejects a definition with %s",
    (_label, mutate) => {
      const definition = structuredClone(PILOT_ASSESSMENT_DEFINITION_V1);
      mutate(definition);
      expect(AssessmentDefinitionSchema.safeParse(definition).success).toBe(
        false,
      );
    },
  );
});

describe("assessment response snapshots", () => {
  it("allows incomplete snapshots for save/resume", () => {
    const responseSet = completeResponseSet();
    responseSet.responses = responseSet.responses.slice(0, 2);

    expect(
      AssessmentResponseSetSchema.parse(responseSet).responses,
    ).toHaveLength(2);
  });

  it("distinguishes a deliberate skip from an unanswered block", () => {
    const responseSet = completeResponseSet();
    responseSet.responses[0] = {
      block_id: "block-1",
      skipped: true,
      most_like_item_id: null,
      least_like_item_id: null,
    };

    expect(AssessmentResponseSetSchema.parse(responseSet).responses[0]).toEqual(
      responseSet.responses[0],
    );
    expect(
      AssessmentResponseSetSchema.safeParse({
        ...responseSet,
        responses: [
          {
            block_id: "block-1",
            skipped: true,
            most_like_item_id: "b1-autonomy",
            least_like_item_id: null,
          },
        ],
      }).success,
    ).toBe(false);
  });

  it("rejects duplicate blocks and identical most/least selections", () => {
    const responseSet = completeResponseSet();
    expect(
      AssessmentResponseSetSchema.safeParse({
        ...responseSet,
        responses: [responseSet.responses[0], responseSet.responses[0]],
      }).success,
    ).toBe(false);

    const response = responseSet.responses[0];
    expect(
      AssessmentResponseSetSchema.safeParse({
        ...responseSet,
        responses: [
          {
            ...response,
            least_like_item_id: response.skipped
              ? null
              : response.most_like_item_id,
          },
        ],
      }).success,
    ).toBe(false);
  });
});

describe("deterministic assessment scoring", () => {
  it("rejects malformed persisted score snapshots", () => {
    const result = scoreAssessment(
      PILOT_ASSESSMENT_DEFINITION_V1,
      completeResponseSet(),
    );
    const duplicateConstruct = structuredClone(result);
    duplicateConstruct.construct_scores[5].construct_key = "autonomy";
    expect(
      AssessmentScoreResultSchema.safeParse(duplicateConstruct).success,
    ).toBe(false);

    const inconsistentCounts = structuredClone(result);
    inconsistentCounts.construct_scores[0].assigned_item_count = 3;
    expect(
      AssessmentScoreResultSchema.safeParse(inconsistentCounts).success,
    ).toBe(false);

    const impossibleRawScore = structuredClone(result);
    impossibleRawScore.construct_scores[0].raw_score = 5;
    expect(
      AssessmentScoreResultSchema.safeParse(impossibleRawScore).success,
    ).toBe(false);
  });

  it.each([
    [-4, 1],
    [-3, 1],
    [-2, 2],
    [-1, 2],
    [0, 3],
    [1, 4],
    [2, 4],
    [3, 5],
    [4, 5],
  ])("maps raw score %i to rating %i", (rawScore, expectedRating) => {
    const score = scoreFor(
      "autonomy",
      responsesForRawScore("autonomy", rawScore),
    );
    expect(score.raw_score).toBe(rawScore);
    expect(score.rating).toBe(expectedRating);
    expect(score.confidence).toBe("high");
    expect(score).toMatchObject({
      assigned_item_count: 4,
      answered_item_count: 4,
      skipped_item_count: 0,
    });
  });

  it("applies the scoring rule to every construct", () => {
    for (const constructKey of CONSTRUCT_KEYS) {
      expect(
        scoreFor(constructKey, responsesForRawScore(constructKey, 4)),
      ).toMatchObject({
        construct_key: constructKey,
        raw_score: 4,
        rating: 5,
        confidence: "high",
      });
      expect(
        scoreFor(constructKey, responsesForRawScore(constructKey, -4)),
      ).toMatchObject({
        construct_key: constructKey,
        raw_score: -4,
        rating: 1,
        confidence: "high",
      });
    }
  });

  it("derives confidence separately from each construct's skipped items", () => {
    const responseSet = completeResponseSet();
    for (const blockId of ["block-1", "block-2"]) {
      const index = responseSet.responses.findIndex(
        (response) => response.block_id === blockId,
      );
      responseSet.responses[index] = {
        block_id: blockId,
        skipped: true,
        most_like_item_id: null,
        least_like_item_id: null,
      };
    }

    const result = scoreAssessment(PILOT_ASSESSMENT_DEFINITION_V1, responseSet);
    expect(
      result.construct_scores.find(
        ({ construct_key }) => construct_key === "autonomy",
      ),
    ).toMatchObject({
      confidence: "low",
      assigned_item_count: 4,
      answered_item_count: 2,
      skipped_item_count: 2,
    });
    expect(
      result.construct_scores.find(
        ({ construct_key }) => construct_key === "structure",
      ),
    ).toMatchObject({ confidence: "medium", skipped_item_count: 1 });
    expect(
      result.construct_scores.find(
        ({ construct_key }) => construct_key === "collaboration",
      ),
    ).toMatchObject({ confidence: "medium", skipped_item_count: 1 });
  });

  it("scores a fully skipped assessment without fabricating responses", () => {
    const responseSet = completeResponseSet();
    responseSet.responses = responseSet.responses.map((response) => ({
      block_id: response.block_id,
      skipped: true,
      most_like_item_id: null,
      least_like_item_id: null,
    }));

    expect(
      scoreAssessment(PILOT_ASSESSMENT_DEFINITION_V1, responseSet)
        .construct_scores,
    ).toEqual(
      CONSTRUCT_KEYS.map((constructKey) => ({
        construct_key: constructKey,
        raw_score: 0,
        rating: 3,
        confidence: "low",
        assigned_item_count: 4,
        answered_item_count: 0,
        skipped_item_count: 4,
      })),
    );
  });

  it("is stable across response and statement display order", () => {
    const responseSet = completeResponseSet();
    const reorderedDefinition = structuredClone(PILOT_ASSESSMENT_DEFINITION_V1);
    reorderedDefinition.blocks.reverse();
    for (const block of reorderedDefinition.blocks) {
      block.items.reverse();
    }

    expect(scoreAssessment(reorderedDefinition, responseSet)).toEqual(
      scoreAssessment(PILOT_ASSESSMENT_DEFINITION_V1, {
        ...responseSet,
        responses: [...responseSet.responses].reverse(),
      }),
    );
  });

  it("does not mutate its definition or response inputs", () => {
    const definition = structuredClone(PILOT_ASSESSMENT_DEFINITION_V1);
    const responseSet = completeResponseSet(definition);
    const originalDefinition = structuredClone(definition);
    const originalResponses = structuredClone(responseSet);

    scoreAssessment(definition, responseSet);

    expect(definition).toEqual(originalDefinition);
    expect(responseSet).toEqual(originalResponses);
  });

  it("persists exact definition and scoring versions in the result", () => {
    const definition = structuredClone(PILOT_ASSESSMENT_DEFINITION_V1);
    definition.version = "1.1.0";
    definition.scoring.version = "2.0.0";
    const responseSet = completeResponseSet(definition);

    expect(scoreAssessment(definition, responseSet)).toMatchObject({
      assessment_definition_id: "work-preferences-pilot",
      assessment_definition_version: "1.1.0",
      scoring_version: "2.0.0",
    });
  });

  it.each([
    [
      "an incomplete response set",
      "incomplete_assessment",
      (responseSet: AssessmentResponseSet) => responseSet.responses.pop(),
    ],
    [
      "an unknown block",
      "unknown_block",
      (responseSet: AssessmentResponseSet) => {
        responseSet.responses[0].block_id = "unknown-block";
      },
    ],
    [
      "an item from another block",
      "invalid_item_selection",
      (responseSet: AssessmentResponseSet) => {
        const response = responseSet.responses[0];
        if (!response.skipped) {
          response.most_like_item_id = "b2-ambiguity";
        }
      },
    ],
  ])("rejects %s", (_label, expectedCode, mutate) => {
    const responseSet = completeResponseSet();
    mutate(responseSet);

    try {
      scoreAssessment(PILOT_ASSESSMENT_DEFINITION_V1, responseSet);
      expect.fail("Expected scoring to reject invalid responses");
    } catch (error) {
      expect(error).toBeInstanceOf(AssessmentScoringError);
      if (!(error instanceof AssessmentScoringError)) {
        expect.fail("Expected an AssessmentScoringError");
      }
      expect(error.code).toBe(expectedCode);
    }
  });

  it("rejects a response snapshot from a different definition version", () => {
    const responseSet = completeResponseSet();
    responseSet.assessment_definition_version = "2.0.0";

    expect(() =>
      scoreAssessment(PILOT_ASSESSMENT_DEFINITION_V1, responseSet),
    ).toThrowError(
      expect.objectContaining<Partial<AssessmentScoringError>>({
        code: "definition_mismatch",
      }),
    );
  });
});
