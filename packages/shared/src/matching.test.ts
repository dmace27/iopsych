import { readFile } from "node:fs/promises";
import path from "node:path";

import { describe, expect, it } from "vitest";

import {
  APPROVED_INTERVIEW_QUESTION_LIBRARY_V1,
  AlignmentClassificationSchema,
  CandidateResponseSummarySchema,
  CONSTRUCT_KEYS,
  MatchingError,
  InterviewQuestionLibrarySchema,
  MatchingResultSchema,
  MatchingRoleProfileSchema,
  RoleEvidenceSummarySchema,
  comparisonRating,
  lowerConfidence,
  matchConstruct,
  matchRoleProfile,
  type AssessmentScoreResult,
  type CandidateConstructScore,
  type ConfidenceLevel,
  type ConstructKey,
  type MatchingRoleProfile,
  type RoleConstructRating,
} from "./index";

function roleRating(
  key: ConstructKey,
  rating = 3,
  confidence: ConfidenceLevel = "high",
): RoleConstructRating {
  return {
    key,
    rating,
    confidence,
    rationale: `Synthetic rationale for ${key}.`,
    evidence: [`Synthetic role evidence for ${key}.`],
  };
}

function candidateScore(
  constructKey: ConstructKey,
  rating = 3,
  confidence: ConfidenceLevel = "high",
): CandidateConstructScore {
  const skipped = { high: 0, medium: 1, low: 2 }[confidence];
  return {
    construct_key: constructKey,
    raw_score: 0,
    rating,
    confidence,
    assigned_item_count: 4,
    answered_item_count: 4 - skipped,
    skipped_item_count: skipped,
  };
}

function roleProfile(approved = true): MatchingRoleProfile {
  return {
    approved,
    constructs: [...CONSTRUCT_KEYS].reverse().map((key) => roleRating(key)),
  };
}

function scoreResult(): AssessmentScoreResult {
  return {
    assessment_definition_id: "synthetic-assessment",
    assessment_definition_version: "2.1.0",
    scoring_version: "3.0.0",
    construct_scores: [...CONSTRUCT_KEYS]
      .reverse()
      .map((key) => candidateScore(key)),
  };
}

describe("matching classification boundaries", () => {
  it.each([
    [1, 1, "aligned", "difference_at_most_one"],
    [1, 2, "aligned", "difference_at_most_one"],
    [1, 3, "worth_discussing", "difference_equals_two"],
    [1, 4, "potential_friction", "difference_at_least_three"],
    [1, 5, "potential_friction", "difference_at_least_three"],
    [5, 4, "aligned", "difference_at_most_one"],
    [5, 3, "worth_discussing", "difference_equals_two"],
    [5, 2, "potential_friction", "difference_at_least_three"],
    [5, 1, "potential_friction", "difference_at_least_three"],
  ] as const)(
    "classifies role %i and candidate %i as %s",
    (roleValue, candidateValue, classification, rule) => {
      const result = matchConstruct(
        roleRating("autonomy", roleValue),
        candidateScore("autonomy", candidateValue),
        true,
      );

      expect(result.classification).toBe(classification);
      expect(result.explanation.applied_rule).toMatchObject({
        rule,
        absolute_difference: Math.abs(roleValue - candidateValue),
      });
      expect(result.explanation.uncertainty).toBeNull();
    },
  );

  it.each(CONSTRUCT_KEYS)("applies common boundaries to %s", (key) => {
    // Three is its own inverse, so this also isolates structure's shared rule.
    expect(
      matchConstruct(roleRating(key, 3), candidateScore(key, 3), true)
        .classification,
    ).toBe("aligned");
    expect(
      matchConstruct(roleRating(key, 3), candidateScore(key, 4), true)
        .classification,
    ).toBe("aligned");
    expect(
      matchConstruct(roleRating(key, 3), candidateScore(key, 5), true)
        .classification,
    ).toBe("worth_discussing");
  });

  it.each([1, 2, 3, 4, 5])("inverts structure role rating %i", (roleValue) => {
    const target = 6 - roleValue;
    const result = matchConstruct(
      roleRating("structure", roleValue),
      candidateScore("structure", target),
      true,
    );

    expect(comparisonRating("structure", roleValue)).toBe(target);
    expect(result.classification).toBe("aligned");
    expect(result.explanation.role).toMatchObject({
      comparison_target: "inverse_role_rating",
      comparison_rating: target,
    });
    expect(result.explanation.applied_rule.absolute_difference).toBe(0);
  });

  it.each(CONSTRUCT_KEYS.filter((key) => key !== "structure"))(
    "uses the direct role rating for %s",
    (key) => {
      expect(
        [1, 2, 3, 4, 5].map((value) => comparisonRating(key, value)),
      ).toEqual([1, 2, 3, 4, 5]);
    },
  );
});

describe("confidence and approval gates", () => {
  const confidenceCases = [
    ["low", "low", "low"],
    ["low", "medium", "low"],
    ["low", "high", "low"],
    ["medium", "low", "low"],
    ["medium", "medium", "medium"],
    ["medium", "high", "medium"],
    ["high", "low", "low"],
    ["high", "medium", "medium"],
    ["high", "high", "high"],
  ] as const;

  it.each(confidenceCases)(
    "combines role %s and candidate %s as %s",
    (roleConfidence, candidateConfidence, expected) => {
      const result = matchConstruct(
        roleRating("pace", 1, roleConfidence),
        candidateScore("pace", 5, candidateConfidence),
        true,
      );

      expect(lowerConfidence(roleConfidence, candidateConfidence)).toBe(
        expected,
      );
      expect(result.confidence).toBe(expected);
      if (expected === "low") {
        expect(result.classification).toBe("insufficient_evidence");
        expect(result.explanation.applied_rule.rule).toBe("low_confidence");
        expect(result.explanation.uncertainty).not.toBeNull();
      } else {
        expect(result.classification).toBe("potential_friction");
      }
    },
  );

  it("fails closed for an unapproved role profile", () => {
    const result = matchRoleProfile(roleProfile(false), scoreResult());

    expect(result.role_profile_approved).toBe(false);
    for (const item of result.items) {
      expect(item.classification).toBe("insufficient_evidence");
      expect(item.explanation.applied_rule.rule).toBe(
        "role_profile_not_approved",
      );
      expect(item.explanation.uncertainty).not.toBeNull();
    }
  });
});

describe("explanations and interview questions", () => {
  it("matches the checked-in language-neutral question library", async () => {
    const contents = await readFile(
      path.resolve(
        import.meta.dirname,
        "..",
        "definitions",
        "v1",
        "interview-questions.json",
      ),
      "utf8",
    );

    expect(JSON.parse(contents)).toEqual(
      APPROVED_INTERVIEW_QUESTION_LIBRARY_V1,
    );
  });

  it("returns traceable evidence, versions, and canonical construct order", () => {
    const result = matchRoleProfile(roleProfile(), scoreResult());

    expect(result).toMatchObject({
      algorithm_version: "1.0.0",
      assessment_definition_id: "synthetic-assessment",
      assessment_definition_version: "2.1.0",
      scoring_version: "3.0.0",
    });
    expect(result.items.map(({ construct_key }) => construct_key)).toEqual(
      CONSTRUCT_KEYS,
    );
    expect(result.items[0].explanation).toMatchObject({
      role: {
        evidence: ["Synthetic role evidence for autonomy."],
        rationale: "Synthetic rationale for autonomy.",
      },
      candidate_response: {
        rating: 3,
        confidence: "high",
        raw_score: 0,
        assigned_item_count: 4,
        answered_item_count: 4,
        skipped_item_count: 0,
      },
    });
  });

  it("has one approved pair for all 24 keys and 48 unique ids", () => {
    const expectedKeys = new Set(
      CONSTRUCT_KEYS.flatMap((constructKey) =>
        AlignmentClassificationSchema.options.map(
          (classification) => `${constructKey}/${classification}`,
        ),
      ),
    );
    const observedKeys = new Set(
      APPROVED_INTERVIEW_QUESTION_LIBRARY_V1.map(
        (entry) => `${entry.construct_key}/${entry.classification}`,
      ),
    );
    const ids = APPROVED_INTERVIEW_QUESTION_LIBRARY_V1.flatMap((entry) => [
      entry.questions.primary.id,
      entry.questions.follow_up.id,
    ]);

    expect(observedKeys).toEqual(expectedKeys);
    expect(
      APPROVED_INTERVIEW_QUESTION_LIBRARY_V1.every(
        ({ review_status }) => review_status === "approved",
      ),
    ).toBe(true);
    expect(ids).toHaveLength(48);
    expect(new Set(ids)).toHaveLength(48);

    const duplicateKey = structuredClone(
      APPROVED_INTERVIEW_QUESTION_LIBRARY_V1,
    );
    duplicateKey[23] = structuredClone(duplicateKey[0]);
    expect(InterviewQuestionLibrarySchema.safeParse(duplicateKey).success).toBe(
      false,
    );
  });

  it("uses the specified ambiguity friction questions", () => {
    const result = matchConstruct(
      roleRating("ambiguity", 1),
      candidateScore("ambiguity", 5),
      true,
    );

    expect(result.interview_questions.primary.text).toBe(
      "Tell me about a time requirements were incomplete or changed quickly. How did you decide what to do next?",
    );
    expect(result.interview_questions.follow_up.text).toBe(
      "What support, information, or routines helped you work effectively?",
    );
  });
});

describe("matching invariants", () => {
  it("is deterministic and does not mutate inputs", () => {
    const profile = roleProfile();
    const scores = scoreResult();
    const originalProfile = structuredClone(profile);
    const originalScores = structuredClone(scores);

    const first = matchRoleProfile(profile, scores);
    const second = matchRoleProfile(profile, scores);

    expect(first).toEqual(second);
    expect(profile).toEqual(originalProfile);
    expect(scores).toEqual(originalScores);
    expect(first).not.toHaveProperty("hire_score");
    expect(first).not.toHaveProperty("recommendation");
  });

  it("rejects mismatched constructs with a stable domain error", () => {
    expect(() =>
      matchConstruct(roleRating("autonomy"), candidateScore("pace"), true),
    ).toThrowError(
      expect.objectContaining<Partial<MatchingError>>({
        code: "construct_mismatch",
      }),
    );
  });

  it("rejects duplicate constructs in input and persisted output", () => {
    const profile = roleProfile();
    profile.constructs[0] = roleRating("autonomy");
    expect(MatchingRoleProfileSchema.safeParse(profile).success).toBe(false);

    const result = matchRoleProfile(roleProfile(), scoreResult());
    result.items[5].construct_key = "autonomy";
    expect(MatchingResultSchema.safeParse(result).success).toBe(false);
  });

  it("rejects impossible candidate response summaries", () => {
    const valid = {
      rating: 3,
      confidence: "high",
      raw_score: 0,
      assigned_item_count: 4,
      answered_item_count: 4,
      skipped_item_count: 0,
    } as const;

    expect(
      CandidateResponseSummarySchema.safeParse({
        ...valid,
        assigned_item_count: 3,
      }).success,
    ).toBe(false);
    expect(
      CandidateResponseSummarySchema.safeParse({
        ...valid,
        assigned_item_count: 5,
        answered_item_count: 5,
      }).success,
    ).toBe(false);
    expect(
      CandidateResponseSummarySchema.safeParse({
        ...valid,
        raw_score: 5,
      }).success,
    ).toBe(false);
  });

  it("rejects an explanation whose stored comparison target cannot be reproduced", () => {
    expect(
      RoleEvidenceSummarySchema.safeParse({
        rating: 5,
        confidence: "high",
        rationale: "Synthetic rationale.",
        evidence: ["Synthetic evidence."],
        comparison_target: "inverse_role_rating",
        comparison_rating: 5,
      }).success,
    ).toBe(false);
  });
});
