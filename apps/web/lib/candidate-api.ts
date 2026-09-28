import { ApiProblemSchema, type AssessmentResponseSet } from "@iopsych/shared";
import type { z } from "zod";

import { ApiClientError } from "./api-client";
import {
  CandidateInviteSchema,
  SubmissionReceiptSchema,
  type CandidateInvite,
  type ConsentDecision,
  type SubmissionReceipt,
} from "./candidate-contracts";

/** Call the same-origin candidate boundary without leaking tokens to third parties. */
async function candidateRequest<T>(
  token: string,
  schema: z.ZodType<T>,
  suffix = "",
  init?: RequestInit,
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(
      `/api/candidate/invites/${encodeURIComponent(token)}${suffix}`,
      {
        ...init,
        cache: "no-store",
        headers: {
          Accept: "application/json",
          ...(init?.body ? { "Content-Type": "application/json" } : {}),
          ...init?.headers,
        },
      },
    );
  } catch {
    throw new ApiClientError("The assessment service could not be reached.", {
      code: "network_error",
      status: 0,
    });
  }

  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const problem = ApiProblemSchema.safeParse(payload);
    throw new ApiClientError(
      problem.success
        ? (problem.data.detail ?? problem.data.title)
        : "This invitation could not be opened.",
      {
        code: problem.success ? problem.data.code : "unexpected_response",
        fieldErrors: problem.success ? problem.data.errors : undefined,
        status: response.status,
      },
    );
  }

  const parsed = schema.safeParse(payload);
  if (!parsed.success) {
    throw new ApiClientError("The invitation response was not recognized.", {
      code: "invalid_api_response",
      status: response.status,
    });
  }
  return parsed.data;
}

/** Load public role and consent-notice context for a bearer invitation. */
export function getCandidateInvite(token: string): Promise<CandidateInvite> {
  return candidateRequest(token, CandidateInviteSchema);
}

/** Record the candidate's terminal, explicit consent decision. */
export function recordCandidateConsent(
  token: string,
  decision: ConsentDecision,
): Promise<CandidateInvite> {
  return candidateRequest(token, CandidateInviteSchema, "/consent", {
    body: JSON.stringify({ decision }),
    method: "POST",
  });
}

/** Persist consented responses and receive a score-free server acknowledgement. */
export function submitCandidateAssessment(
  token: string,
  responses: AssessmentResponseSet,
): Promise<SubmissionReceipt> {
  return candidateRequest(token, SubmissionReceiptSchema, "/submit", {
    method: "POST",
    body: JSON.stringify(responses),
  });
}
