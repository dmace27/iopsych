import trace0 from "../../api/tests/fixtures/report_trace/complete.trace.json";
import source0 from "../../api/tests/fixtures/report_trace/complete.source.json";
import trace1 from "../../api/tests/fixtures/report_trace/skipped.trace.json";
import source1 from "../../api/tests/fixtures/report_trace/skipped.source.json";
import trace2 from "../../api/tests/fixtures/report_trace/two-skipped.trace.json";
import source2 from "../../api/tests/fixtures/report_trace/two-skipped.source.json";
import trace3 from "../../api/tests/fixtures/report_trace/all-skipped.trace.json";
import source3 from "../../api/tests/fixtures/report_trace/all-skipped.source.json";
const fixtures = {
  complete: { trace: trace0, source: source0 },
  skipped: { trace: trace1, source: source1 },
  "two-skipped": { trace: trace2, source: source2 },
  "all-skipped": { trace: trace3, source: source3 },
};
import { ReportSchema } from "./report-contracts";
export function traceFixture(name = "complete") {
  const read = (suffix: "source" | "trace") =>
    JSON.parse(JSON.stringify(fixtures[name as keyof typeof fixtures][suffix]));
  const source = read("source");
  return {
    trace: read("trace"),
    report: ReportSchema.parse({
      id: source.report_id,
      assessment_id: source.assessment_id,
      role_profile_id: source.role_profile_id,
      role_profile_version: source.role_profile_version,
      generated_at: "2026-11-04T12:00:00Z",
      usage_warning: "Synthetic interview preparation only.",
      result: source.result_json,
    }),
  };
}
