import { CONSTRUCT_KEYS, CONSTRUCT_DEFINITIONS_BY_KEY } from "@iopsych/shared";
import { describe, expect, it } from "vitest";

describe("shared domain contracts", () => {
  it("are importable by the web workspace", () => {
    expect(CONSTRUCT_KEYS).toHaveLength(6);
    expect(CONSTRUCT_DEFINITIONS_BY_KEY.structure.comparison_target).toBe(
      "inverse_role_rating",
    );
  });
});
