import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { reportFixture, sourceFixture } from "../app/reports/report-fixtures";
import {
  generateReport,
  getReport,
  getSubmittedAssessments,
} from "./api-client";
beforeEach(() => vi.stubGlobal("fetch", vi.fn()));
afterEach(() => vi.unstubAllGlobals());
it("reads validated reports and paginated sources without caching", async () => {
  vi.mocked(fetch)
    .mockResolvedValueOnce(Response.json(reportFixture))
    .mockResolvedValueOnce(Response.json([sourceFixture]));
  await expect(getReport(reportFixture.id)).resolves.toEqual(reportFixture);
  await expect(getSubmittedAssessments("role/id", 50)).resolves.toEqual([
    sourceFixture,
  ]);
  expect(fetch).toHaveBeenLastCalledWith(
    "/api/internal/roles/role%2Fid/assessments?limit=50&offset=50",
    expect.objectContaining({ cache: "no-store" }),
  );
});
it("generates from authoritative source identifiers only", async () => {
  vi.mocked(fetch).mockResolvedValue(Response.json(reportFixture));
  await expect(generateReport(sourceFixture)).resolves.toEqual(reportFixture);
  expect(fetch).toHaveBeenCalledWith(
    "/api/internal/reports",
    expect.objectContaining({
      method: "POST",
      body: JSON.stringify({
        assessment_id: sourceFixture.assessment_id,
        role_profile_id: sourceFixture.role_profile_id,
      }),
    }),
  );
});
it.each([
  { ...reportFixture, result: { ...reportFixture.result, items: [] } },
  {
    ...reportFixture,
    result: { ...reportFixture.result, role_profile_approved: false },
  },
  { ...reportFixture, composite_score: 99 },
])(
  "rejects malformed or unapproved reports before rendering",
  async (payload) => {
    vi.mocked(fetch).mockResolvedValue(Response.json(payload));
    await expect(getReport(reportFixture.id)).rejects.toMatchObject({
      code: "invalid_api_response",
    });
  },
);
