import { z } from "zod";

import {
  AssessmentDefinitionSchema,
  AssessmentResponseSetSchema,
  AssessmentScoreResultSchema,
} from "./assessment";
import { CONSTRUCT_KEYS, ConstructDefinitionSchema } from "./constructs";
import {
  InterviewQuestionLibrarySchema,
  MatchingResultSchema,
  MatchingRoleProfileSchema,
} from "./matching";
import { ApiProblemSchema } from "./problem-details";
import { RoleExtractionSchema } from "./role-extraction";
import { ScoringConfigSchema } from "./scoring-config";

type JsonSchema = Readonly<Record<string, unknown>>;

function createJsonSchema(
  schema: z.ZodType,
  id: string,
  title: string,
): JsonSchema {
  return {
    $id: `https://iopsych.local/contracts/v1/${id}`,
    title,
    ...z.toJSONSchema(schema, { target: "draft-2020-12" }),
  };
}

function isJsonObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/** Add the cross-item constraint that Zod emits as an in-memory refinement. */
function requireEveryConstructKey(schema: JsonSchema): JsonSchema {
  const properties = schema["properties"];
  if (!isJsonObject(properties) || !isJsonObject(properties["constructs"])) {
    throw new Error("Generated role extraction schema has an unexpected shape");
  }

  return {
    ...schema,
    properties: {
      ...properties,
      constructs: {
        ...properties["constructs"],
        allOf: CONSTRUCT_KEYS.map((key) => ({
          contains: {
            type: "object",
            properties: { key: { const: key } },
            required: ["key"],
          },
          minContains: 1,
          maxContains: 1,
        })),
      },
    },
  };
}

/** Checked-in JSON Schema documents are generated from these Zod contracts. */
export const JSON_SCHEMA_DOCUMENTS = {
  "assessment-definition.schema.json": createJsonSchema(
    AssessmentDefinitionSchema,
    "assessment-definition.schema.json",
    "Assessment definition",
  ),
  "assessment-response-set.schema.json": createJsonSchema(
    AssessmentResponseSetSchema,
    "assessment-response-set.schema.json",
    "Assessment response set",
  ),
  "assessment-score-result.schema.json": createJsonSchema(
    AssessmentScoreResultSchema,
    "assessment-score-result.schema.json",
    "Assessment score result",
  ),
  "api-problem.schema.json": createJsonSchema(
    ApiProblemSchema,
    "api-problem.schema.json",
    "API problem details",
  ),
  "construct-definition.schema.json": createJsonSchema(
    ConstructDefinitionSchema,
    "construct-definition.schema.json",
    "Construct definition",
  ),
  "interview-question-library.schema.json": createJsonSchema(
    InterviewQuestionLibrarySchema,
    "interview-question-library.schema.json",
    "Approved interview-question library",
  ),
  "matching-result.schema.json": createJsonSchema(
    MatchingResultSchema,
    "matching-result.schema.json",
    "Matching result",
  ),
  "matching-role-profile.schema.json": createJsonSchema(
    MatchingRoleProfileSchema,
    "matching-role-profile.schema.json",
    "Matching role profile",
  ),
  "role-extraction.schema.json": requireEveryConstructKey(
    createJsonSchema(
      RoleExtractionSchema,
      "role-extraction.schema.json",
      "Role extraction",
    ),
  ),
  "scoring-config.schema.json": createJsonSchema(
    ScoringConfigSchema,
    "scoring-config.schema.json",
    "Assessment scoring configuration",
  ),
} as const;
