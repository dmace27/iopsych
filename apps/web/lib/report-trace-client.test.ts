import { afterEach, describe, expect, it, vi } from "vitest";
import { traceFixture } from "./report-trace-fixtures";
import {
  parseReportTrace,
  ReportTraceV1Schema,
} from "./report-trace-contracts";
import { getReportTrace } from "./report-trace-client";

afterEach(() => vi.unstubAllGlobals());

describe("strict historical report trace", () => {
  it.each(["1.0.0", "2.0.0"])(
    "requires consistent %s algorithm provenance",
    (algorithm) => {
      const { trace, report } = traceFixture();
      trace.algorithm_version = algorithm;
      for (const construct of trace.constructs) {
        construct.question_selection.algorithm_version = algorithm;
      }
      expect(ReportTraceV1Schema.safeParse(trace).success).toBe(true);
      trace.constructs[0].question_selection.algorithm_version =
        algorithm === "1.0.0" ? "2.0.0" : "1.0.0";
      expect(ReportTraceV1Schema.safeParse(trace).success).toBe(false);
      expect(() => parseReportTrace(trace, report)).toThrow();
    },
  );
  it.each(["complete", "skipped", "two-skipped", "all-skipped"])(
    "accepts exact backend %s fixture",
    (name) => {
      const { trace, report } = traceFixture(name);
      expect(
        parseReportTrace(trace, report).constructs.flatMap(
          (construct) => construct.items,
        ),
      ).toHaveLength(24);
    },
  );
  it.each([
    (trace: ReturnType<typeof traceFixture>["trace"]) => {
      trace.extra = true;
    },
    (trace: ReturnType<typeof traceFixture>["trace"]) => {
      trace.trace_version = "2.0.0";
    },
    (trace: ReturnType<typeof traceFixture>["trace"]) => {
      trace.constructs[0].items.pop();
    },
    (trace: ReturnType<typeof traceFixture>["trace"]) => {
      trace.constructs.reverse();
    },
    (trace: ReturnType<typeof traceFixture>["trace"]) => {
      trace.constructs[0].items[0].contribution = 0;
    },
    (trace: ReturnType<typeof traceFixture>["trace"]) => {
      trace.constructs[0].items[0].most_like_item_id = "missing";
    },
    (trace: ReturnType<typeof traceFixture>["trace"]) => {
      trace.constructs[0].rating_threshold.minimum_raw_score = -4;
    },
    (trace: ReturnType<typeof traceFixture>["trace"]) => {
      trace.constructs[0].confidence_rule = {
        level: "low",
        minimum_skipped_items: 2,
        maximum_skipped_items: null,
      };
    },
    (trace: ReturnType<typeof traceFixture>["trace"]) => {
      trace.report_id = "00000000-0000-4000-8000-000000000099";
    },
    (trace: ReturnType<typeof traceFixture>["trace"]) => {
      trace.assessment_id = "00000000-0000-4000-8000-000000000099";
    },
    (trace: ReturnType<typeof traceFixture>["trace"]) => {
      trace.constructs[0].question_selection.primary_question_id = "wrong";
    },
    (trace: ReturnType<typeof traceFixture>["trace"]) => {
      trace.constructs[0].items[0].extra = true;
    },
  ])("rejects inconsistent/unknown data %#", (mutate) => {
    const { trace, report } = traceFixture();
    mutate(trace);
    expect(() => parseReportTrace(trace, report)).toThrow();
  });
  it("fetches only the report-specific resource without caching and with abort", async () => {
    const { trace, report } = traceFixture();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json(trace)));
    const controller = new AbortController();
    await expect(getReportTrace(report, controller.signal)).resolves.toEqual(
      trace,
    );
    expect(fetch).toHaveBeenCalledWith(
      `/api/internal/reports/${report.id}/trace`,
      {
        signal: controller.signal,
        cache: "no-store",
        headers: { Accept: "application/json" },
      },
    );
  });
  it.each([401, 403, 404, 409, 410, 500])(
    "preserves status %i without exposing payload",
    async (status) => {
      vi.stubGlobal(
        "fetch",
        vi
          .fn()
          .mockResolvedValue(Response.json({ private: "hidden" }, { status })),
      );
      await expect(
        getReportTrace(traceFixture().report, new AbortController().signal),
      ).rejects.toMatchObject({
        status,
        message: "Item-level evidence unavailable for this saved report",
      });
    },
  );
  it("rejects malformed success responses", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json({})));
    await expect(
      getReportTrace(traceFixture().report, new AbortController().signal),
    ).rejects.toMatchObject({ code: "invalid_api_response" });
  });
});

it("normalizes network failure and preserves an explicit abort", async () => {
  const error = new DOMException("Aborted", "AbortError");
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(error));
  const controller = new AbortController();
  await expect(
    getReportTrace(traceFixture().report, controller.signal),
  ).rejects.toMatchObject({ code: "network_error" });
  controller.abort();
  await expect(
    getReportTrace(traceFixture().report, controller.signal),
  ).rejects.toBe(error);
});
it("rejects disagreement with stored aggregate evidence", () => {
  const { trace, report } = traceFixture();
  report.result.items[0].explanation.candidate_response.raw_score = 0;
  expect(() => parseReportTrace(trace, report)).toThrow(
    "Trace evidence mismatch",
  );
});
