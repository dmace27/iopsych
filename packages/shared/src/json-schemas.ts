import { z } from "zod";

import { CONSTRUCT_KEYS, ConstructDefinitionSchema } from "./constructs";
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
