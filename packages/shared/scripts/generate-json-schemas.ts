import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { format } from "prettier";

import { JSON_SCHEMA_DOCUMENTS } from "../src/json-schemas";
import { CONSTRUCT_DEFINITIONS, CONTRACT_VERSION } from "../src/constructs";
import {
  APPROVED_INTERVIEW_QUESTION_LIBRARY_V1,
  MATCHING_ALGORITHM_VERSION,
} from "../src/matching";
import { PILOT_ASSESSMENT_DEFINITION_V1 } from "../src/pilot-assessment";

const packageRoot = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
);
const outputDirectory = path.join(packageRoot, "schemas", "v1");

await mkdir(outputDirectory, { recursive: true });

await Promise.all(
  Object.entries(JSON_SCHEMA_DOCUMENTS).map(async ([filename, schema]) => {
    const output = await format(JSON.stringify(schema), { parser: "json" });
    await writeFile(path.join(outputDirectory, filename), output, "utf8");
  }),
);

const definitionDirectory = path.join(packageRoot, "definitions", "v1");
await mkdir(definitionDirectory, { recursive: true });
await writeFile(
  path.join(definitionDirectory, "pilot-assessment.json"),
  await format(JSON.stringify(PILOT_ASSESSMENT_DEFINITION_V1), {
    parser: "json",
  }),
  "utf8",
);
await writeFile(
  path.join(definitionDirectory, "interview-questions.json"),
  await format(JSON.stringify(APPROVED_INTERVIEW_QUESTION_LIBRARY_V1), {
    parser: "json",
  }),
  "utf8",
);

// Keep the original v1 metadata immutable for historical interpretation.
const currentDefinitionDirectory = path.join(packageRoot, "definitions", "v2");
await mkdir(currentDefinitionDirectory, { recursive: true });
await writeFile(
  path.join(currentDefinitionDirectory, "constructs.json"),
  await format(
    JSON.stringify({
      contract_version: CONTRACT_VERSION,
      matching_algorithm_version: MATCHING_ALGORITHM_VERSION,
      constructs: CONSTRUCT_DEFINITIONS,
    }),
    { parser: "json" },
  ),
  "utf8",
);
