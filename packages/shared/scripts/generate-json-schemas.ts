import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { JSON_SCHEMA_DOCUMENTS } from "../src/json-schemas";

const packageRoot = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
);
const outputDirectory = path.join(packageRoot, "schemas", "v1");

await mkdir(outputDirectory, { recursive: true });

await Promise.all(
  Object.entries(JSON_SCHEMA_DOCUMENTS).map(async ([filename, schema]) => {
    const output = `${JSON.stringify(schema, null, 2)}\n`;
    await writeFile(path.join(outputDirectory, filename), output, "utf8");
  }),
);
