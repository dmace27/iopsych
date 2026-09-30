import { ApiProblemSchema, type ApiFieldError } from "@iopsych/shared";
import type { z } from "zod";

import {
  CurrentUserSchema,
  RoleListSchema,
  RoleProfileListSchema,
  RoleProfileSchema,
  RoleSchema,
  type CurrentUser,
  type Role,
  type RoleCreateInput,
  type RoleProfile,
  type RoleProfileInput,
} from "./contracts";
import {
  ReportSchema,
  SubmittedAssessmentListSchema,
  type Report,
  type SubmittedAssessment,
} from "./report-contracts";
import {
  CandidateDataExportSchema,
  CandidateDeletionSchema,
  PrivacyAuditEventListSchema,
  PrivacyStatusSchema,
  RetentionRunSchema,
  type CandidateDataExport,
  type CandidateDeletion,
  type PrivacyAuditEvent,
  type PrivacyStatus,
  type RetentionRun,
} from "./privacy-contracts";

/** A safe client-facing representation of an API problem response. */
export class ApiClientError extends Error {
  readonly status: number;
  readonly code: string;
  readonly fieldErrors: ApiFieldError[];

  constructor(
    message: string,
    options: { status: number; code: string; fieldErrors?: ApiFieldError[] },
  ) {
    super(message);
    this.name = "ApiClientError";
    this.status = options.status;
    this.code = options.code;
    this.fieldErrors = options.fieldErrors ?? [];
  }
}

/** Parse a successful JSON response and normalize API/network failures. */
async function requestJson<T>(
  path: string,
  schema: z.ZodType<T>,
  init?: RequestInit,
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api/internal${path}`, {
      ...init,
      cache: "no-store",
      headers: {
        Accept: "application/json",
        ...(init?.body ? { "Content-Type": "application/json" } : {}),
        ...init?.headers,
      },
    });
  } catch {
    throw new ApiClientError("The API could not be reached. Try again.", {
      status: 0,
      code: "network_error",
    });
  }

  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const problem = ApiProblemSchema.safeParse(payload);
    throw new ApiClientError(
      problem.success
        ? (problem.data.detail ?? problem.data.title)
        : "The request could not be completed.",
      {
        status: response.status,
        code: problem.success ? problem.data.code : "unexpected_response",
        fieldErrors: problem.success ? problem.data.errors : undefined,
      },
    );
  }

  const parsed = schema.safeParse(payload);
  if (!parsed.success) {
    throw new ApiClientError("The API returned an unexpected response.", {
      status: response.status,
      code: "invalid_api_response",
    });
  }
  return parsed.data;
}

/** Load current user state from the authenticated FastAPI boundary. */
export function getCurrentUser(): Promise<CurrentUser> {
  return requestJson("/auth/me", CurrentUserSchema);
}

/** Load roles belonging to the current organization. */
export function getRoles(): Promise<Role[]> {
  return requestJson("/roles", RoleListSchema);
}

/** Load one organization-scoped role. */
export function getRole(roleId: string): Promise<Role> {
  return requestJson(`/roles/${encodeURIComponent(roleId)}`, RoleSchema);
}

/** Create a draft role through the package 1B endpoint. */
export function createRole(input: RoleCreateInput): Promise<Role> {
  return requestJson("/roles", RoleSchema, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

/** Load complete profile history in ascending version order. */
export function getRoleProfiles(roleId: string): Promise<RoleProfile[]> {
  return requestJson(
    `/roles/${encodeURIComponent(roleId)}/profiles`,
    RoleProfileListSchema,
  );
}

/** Generate a validated draft from the stored role description. */
export function extractRoleProfile(roleId: string): Promise<RoleProfile> {
  return requestJson(
    `/roles/${encodeURIComponent(roleId)}/extract-profile`,
    RoleProfileSchema,
    { method: "POST" },
  );
}

/** Create a complete initial or replacement draft profile. */
export function createRoleProfile(
  roleId: string,
  input: RoleProfileInput,
): Promise<RoleProfile> {
  return requestJson(
    `/roles/${encodeURIComponent(roleId)}/profiles`,
    RoleProfileSchema,
    { method: "POST", body: JSON.stringify(input) },
  );
}

/** Save construct edits as a new immutable profile version. */
export function reviseRoleProfile(
  roleId: string,
  profileId: string,
  input: RoleProfileInput,
): Promise<RoleProfile> {
  return requestJson(
    `/roles/${encodeURIComponent(roleId)}/profiles/${encodeURIComponent(profileId)}`,
    RoleProfileSchema,
    { method: "PATCH", body: JSON.stringify(input) },
  );
}

/** Approve the latest draft through the hiring-manager-only endpoint. */
export function approveRoleProfile(
  roleId: string,
  profileId: string,
): Promise<RoleProfile> {
  return requestJson(
    `/roles/${encodeURIComponent(roleId)}/profiles/${encodeURIComponent(profileId)}/approve`,
    RoleProfileSchema,
    { method: "POST" },
  );
}

/** Discover report sources in chronological order, preserving server pagination. */
export function getSubmittedAssessments(
  roleId: string,
  offset = 0,
): Promise<SubmittedAssessment[]> {
  return requestJson(
    `/roles/${encodeURIComponent(roleId)}/assessments?limit=50&offset=${offset}`,
    SubmittedAssessmentListSchema,
  );
}

export function getReport(reportId: string): Promise<Report> {
  return requestJson(`/reports/${encodeURIComponent(reportId)}`, ReportSchema);
}

/** Submit identifiers only; scoring and approval remain authoritative on the server. */
export function generateReport(
  assessment: SubmittedAssessment,
): Promise<Report> {
  return requestJson("/reports", ReportSchema, {
    method: "POST",
    body: JSON.stringify({
      assessment_id: assessment.assessment_id,
      role_profile_id: assessment.role_profile_id,
    }),
  });
}

/** Load tenant retention counts for the administrator privacy workspace. */
export function getPrivacyStatus(): Promise<PrivacyStatus> {
  return requestJson("/privacy/status", PrivacyStatusSchema);
}

/** Read newest-first immutable audit history, optionally for one entity. */
export function getPrivacyAuditEvents(
  entityId?: string,
  before?: string,
  limit = 50,
): Promise<PrivacyAuditEvent[]> {
  const parameters = new URLSearchParams();
  if (entityId) parameters.set("entity_id", entityId);
  if (before) parameters.set("before", before);
  if (limit !== 50) parameters.set("limit", String(limit));
  const serialized = parameters.toString();
  const query = serialized ? `?${serialized}` : "";
  return requestJson(
    `/privacy/audit-events${query}`,
    PrivacyAuditEventListSchema,
  );
}

/** Create a no-store portable export for one tenant-owned assessment. */
export function exportCandidateData(
  assessmentId: string,
): Promise<CandidateDataExport> {
  return requestJson(
    `/candidates/${encodeURIComponent(assessmentId)}/export`,
    CandidateDataExportSchema,
    { method: "POST" },
  );
}

/** Irreversibly anonymize one candidate and their derived reports. */
export function deleteCandidateData(
  assessmentId: string,
): Promise<CandidateDeletion> {
  return requestJson(
    `/candidates/${encodeURIComponent(assessmentId)}`,
    CandidateDeletionSchema,
    { method: "DELETE" },
  );
}

/** Run one bounded retention batch for the active organization. */
export function runPrivacyRetention(): Promise<RetentionRun> {
  return requestJson("/privacy/retention/run", RetentionRunSchema, {
    method: "POST",
  });
}
