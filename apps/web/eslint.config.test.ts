import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { tmpdir } from "node:os";
import { join, relative } from "node:path";
import { afterAll, beforeAll, describe, expect, it } from "vitest";

// Exercise the installed plugin so an upstream API change fails this check.
const require = createRequire(import.meta.url);
const { getRootDirs } =
  require("@next/eslint-plugin-next/dist/utils/get-root-dirs.js") as {
    getRootDirs(context: {
      cwd: string;
      settings: { next: { rootDir?: string | string[] } };
    }): string[];
  };

describe("Next.js lint root discovery with the safe glob override", () => {
  let fixtureRoot: string;

  beforeAll(() => {
    fixtureRoot = mkdtempSync(join(tmpdir(), "iopsych-eslint-"));
    for (const app of ["web", "admin"]) {
      mkdirSync(join(fixtureRoot, app, "app"), { recursive: true });
    }
    writeFileSync(join(fixtureRoot, "package.json"), "{}");
  });

  afterAll(() => rmSync(fixtureRoot, { recursive: true, force: true }));

  const discover = (rootDir?: string | string[]) =>
    getRootDirs({ cwd: fixtureRoot, settings: { next: { rootDir } } }).sort();

  it("defaults to the ESLint working directory", () => {
    expect(discover()).toEqual([fixtureRoot]);
  });

  it("keeps an absolute root without recursively adding its children", () => {
    expect(discover(join(fixtureRoot, "web"))).toEqual([
      join(fixtureRoot, "web"),
    ]);
    expect(discover(`${fixtureRoot}/web/`)).toEqual([`${fixtureRoot}/web/`]);
  });

  it("matches directory globs and brace patterns without including files", () => {
    const expected = [join(fixtureRoot, "admin"), join(fixtureRoot, "web")];
    expect(discover(`${fixtureRoot}/*`)).toEqual(expected);
    expect(discover(`${fixtureRoot}/{web,admin}`)).toEqual(expected);
  });

  it("preserves relative directory paths", () => {
    const rootDir = relative(process.cwd(), join(fixtureRoot, "web"));
    expect(discover(rootDir)).toEqual([rootDir]);
    expect(discover(`${rootDir}/`)).toEqual([`${rootDir}/`]);
  });

  it("accepts arrays of roots and ignores missing directories", () => {
    expect(
      discover([
        join(fixtureRoot, "web"),
        join(fixtureRoot, "admin"),
        join(fixtureRoot, "missing"),
      ]),
    ).toEqual([join(fixtureRoot, "admin"), join(fixtureRoot, "web")]);
  });
});
