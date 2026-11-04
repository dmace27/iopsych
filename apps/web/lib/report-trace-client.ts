import { ApiProblemSchema } from "@iopsych/shared";
import { ApiClientError } from "./api-client";
import type { Report } from "./report-contracts";
import { parseReportTrace } from "./report-trace-contracts";

export async function getReportTrace(report: Report, signal: AbortSignal) {
  let response: Response;
  try {
    response = await fetch(
      `/api/internal/reports/${encodeURIComponent(report.id)}/trace`,
      {
        signal,
        cache: "no-store",
        headers: { Accept: "application/json" },
      },
    );
  } catch (error) {
    if (signal.aborted) throw error;
    throw new ApiClientError("Item-level evidence could not be reached.", {
      status: 0,
      code: "network_error",
    });
  }
  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const problem = ApiProblemSchema.safeParse(payload);
    throw new ApiClientError(
      "Item-level evidence unavailable for this saved report",
      {
        status: response.status,
        code: problem.success ? problem.data.code : "unexpected_response",
      },
    );
  }
  try {
    return parseReportTrace(payload, report);
  } catch {
    throw new ApiClientError(
      "Item-level evidence unavailable for this saved report",
      { status: response.status, code: "invalid_api_response" },
    );
  }
}
