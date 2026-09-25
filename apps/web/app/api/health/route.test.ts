import { describe, expect, it } from "vitest";

import { GET } from "./route";

describe("GET /api/health", () => {
  it("returns stable service metadata", async () => {
    const response = GET();

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual({
      service: "web",
      status: "ok",
      version: "0.1.0",
    });
  });
});
