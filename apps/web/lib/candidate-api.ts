import { ApiProblemSchema } from "@iopsych/shared";

import { ApiClientError } from "./api-client";
import {
  CandidateInviteSchema,
  type CandidateInvite,
  type ConsentDecision,
} from "./candidate-contracts";

/** Call the same-origin candidate boundary without leaking tokens to third parties. */
async function candidateRequest(
  token: string,
  suffix = "",
  init?: RequestInit,
): Promise<CandidateInvite> {
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

  const parsed = CandidateInviteSchema.safeParse(payload);
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
  return candidateRequest(token);
}

/** Record the candidate's terminal, explicit consent decision. */
export function recordCandidateConsent(
  token: string,
  decision: ConsentDecision,
): Promise<CandidateInvite> {
  return candidateRequest(token, "/consent", {
    body: JSON.stringify({ decision }),
    method: "POST",
  });
}
