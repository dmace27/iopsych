import { readFile } from "node:fs/promises";
import path from "node:path";

import { describe, expect, it } from "vitest";

import {
  AlignmentClassificationSchema,
  ApiProblemSchema,
  CONSTRUCT_DEFINITIONS,
  CONSTRUCT_DEFINITIONS_BY_KEY,
  CONSTRUCT_KEYS,
  ConfidenceLevelSchema,
  JSON_SCHEMA_DOCUMENTS,
  parseRoleExtraction,
  RatingSchema,
  RoleExtractionSchema,
  ScoringConfigSchema,
} from "./index";

type FixtureCase = {
  contract: "api_problem" | "role_extraction" | "scoring_config";
  expected_valid: boolean;
  payload: unknown;
  context?: {
    job_description?: string;
  };
};

const packageRoot = path.resolve(import.meta.dirname, "..");

async function loadFixture(relativePath: string): Promise<FixtureCase> {
  const contents = await readFile(
    path.join(packageRoot, "fixtures", "v1", relativePath),
    "utf8",
  );
  return JSON.parse(contents) as FixtureCase;
}

function validateFixture(fixture: FixtureCase): boolean {
  switch (fixture.contract) {
    case "api_problem":
      return ApiProblemSchema.safeParse(fixture.payload).success;
    case "scoring_config":
      return ScoringConfigSchema.safeParse(fixture.payload).success;
    case "role_extraction": {
      const jobDescription = fixture.context?.job_description;
      if (jobDescription === undefined) {
        return false;
      }

      try {
        parseRoleExtraction(fixture.payload, jobDescription);
        return true;
      } catch {
        return false;
      }
    }
  }
}

describe("construct contract", () => {
  it("matches the canonical language-neutral definitions", async () => {
    const contents = await readFile(
      path.join(packageRoot, "definitions", "v1", "constructs.json"),
      "utf8",
    );
    const document = JSON.parse(contents) as {
      contract_version: string;
      constructs: unknown;
    };

    expect(document.contract_version).toBe("1.0.0");
    expect(document.constructs).toEqual(CONSTRUCT_DEFINITIONS);
  });

  it("defines exactly the six version 1 constructs", () => {
    expect(CONSTRUCT_KEYS).toEqual([
      "autonomy",
      "structure",
      "ambiguity",
      "collaboration",
      "mastery",
      "pace",
    ]);
    expect(CONSTRUCT_DEFINITIONS).toHaveLength(6);
  });

  it("keeps the exceptional structure comparison target explicit", () => {
    expect(CONSTRUCT_DEFINITIONS_BY_KEY.structure.comparison_target).toBe(
      "inverse_role_rating",
    );
    expect(
      CONSTRUCT_DEFINITIONS.filter(({ key }) => key !== "structure").every(
        ({ comparison_target }) => comparison_target === "role_rating",
      ),
    ).toBe(true);
  });

  it("enforces rating, confidence, and classification enums", () => {
    expect(RatingSchema.safeParse(1).success).toBe(true);
    expect(RatingSchema.safeParse(5).success).toBe(true);
    expect(RatingSchema.safeParse(0).success).toBe(false);
    expect(RatingSchema.safeParse(6).success).toBe(false);
    expect(ConfidenceLevelSchema.options).toEqual(["low", "medium", "high"]);
    expect(AlignmentClassificationSchema.options).toEqual([
      "aligned",
      "worth_discussing",
      "potential_friction",
      "insufficient_evidence",
    ]);
  });
});

describe("shared fixture cases", () => {
  const fixturePaths = [
    "api-problem/valid.json",
    "api-problem/invalid-status.json",
    "role-extraction/valid.json",
    "role-extraction/invalid-evidence.json",
    "role-extraction/invalid-missing-construct.json",
    "scoring-config/valid.json",
    "scoring-config/invalid-gap.json",
  ] as const;

  for (const fixturePath of fixturePaths) {
    it(`validates ${fixturePath}`, async () => {
      const fixture = await loadFixture(fixturePath);
      expect(validateFixture(fixture)).toBe(fixture.expected_valid);
    });
  }
});

describe("role extraction contract", () => {
  it("rejects unrecognized fields and cannot activate a profile", async () => {
    const fixture = await loadFixture("role-extraction/valid.json");
    const payload = {
      ...(fixture.payload as Record<string, unknown>),
      needs_human_review: false,
      approved: true,
    };

    expect(RoleExtractionSchema.safeParse(payload).success).toBe(false);
  });

  it("requires source context for evidence validation", async () => {
    const fixture = await loadFixture("role-extraction/valid.json");
    expect(() => parseRoleExtraction(fixture.payload, "   ")).toThrow(
      "A non-empty job description is required",
    );
  });
});

describe("API problem contract", () => {
  it("requires field locations to be JSON Pointers", () => {
    expect(
      ApiProblemSchema.safeParse({
        title: "Invalid request",
        status: 422,
        code: "invalid_request",
        errors: [
          { pointer: "title", code: "required", message: "Title is required." },
        ],
      }).success,
    ).toBe(false);
  });
});

describe("versioned JSON Schema artifacts", () => {
  for (const [filename, generatedSchema] of Object.entries(
    JSON_SCHEMA_DOCUMENTS,
  )) {
    it(`keeps ${filename} synchronized with its TypeScript schema`, async () => {
      const contents = await readFile(
        path.join(packageRoot, "schemas", "v1", filename),
        "utf8",
      );
      expect(JSON.parse(contents)).toEqual(generatedSchema);
    });
  }

  it("requires every construct key exactly once in role extraction JSON", () => {
    const serializedSchema = JSON.stringify(
      JSON_SCHEMA_DOCUMENTS["role-extraction.schema.json"],
    );
    expect(serializedSchema.match(/maxContains/g)).toHaveLength(6);
    for (const key of CONSTRUCT_KEYS) {
      expect(serializedSchema).toContain(`"const":"${key}"`);
    }
  });
});
