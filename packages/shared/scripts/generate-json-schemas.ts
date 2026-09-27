import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { format } from "prettier";

import { JSON_SCHEMA_DOCUMENTS } from "../src/json-schemas";
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
