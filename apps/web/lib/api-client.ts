import {
  InvitationSchema,
  InvitationReissueSchema,
  ProviderInvitationDeliverySchema,
} from "./invitation-contracts";
import { ApiProblemSchema, type ApiFieldError } from "@iopsych/shared";
import type { z } from "zod";

import {
  CurrentUserSchema,
  ManagedUserSchema,
  type ManagedUser,
  type ManagedUserInput,
  type InternalUserRole,
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
  PrivacyAssessmentListSchema,
  PrivacyAssessmentLookupSchema,
  type PrivacyAssessmentList,
  type PrivacyAssessmentLookup,
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
    // Let account navigation offer recovery as soon as any workspace loses its session.
    if (response.status === 401 && typeof window !== "undefined") {
      window.dispatchEvent(new Event("iopsych:session-expired"));
    }
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

/** Read newest-first immutable audit history for an entity or related assessment. */
export function getPrivacyAuditEvents(
  scope?: string | { assessment_id: string },
  before?: string,
  limit = 50,
): Promise<PrivacyAuditEvent[]> {
  const parameters = new URLSearchParams();
  if (typeof scope === "string" && scope) parameters.set("entity_id", scope);
  else if (typeof scope === "object")
    parameters.set("assessment_id", scope.assessment_id);
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
    { method: "POST", headers: { "X-IOPsych-Notice-Snapshot": "1" } },
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

/** Discover a bounded page by exactly one tenant-scoped reference. */
export async function getPrivacyAssessments(
  lookup: PrivacyAssessmentLookup,
): Promise<PrivacyAssessmentList> {
  const parsed = PrivacyAssessmentLookupSchema.safeParse(lookup);
  if (!parsed.success) {
    throw new ApiClientError(
      "Enter one valid invitation or role reference and bounded pagination values.",
      { status: 422, code: "invalid_privacy_lookup" },
    );
  }
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(parsed.data)) {
    if (value !== undefined) params.set(key, String(value));
  }
  return requestJson(
    `/privacy/assessments?${params}`,
    PrivacyAssessmentListSchema,
  );
}
/** Read a bounded page of accounts in the administrator's organization. */
export function getManagedUsers(offset = 0): Promise<ManagedUser[]> {
  return requestJson(
    `/users?limit=50&offset=${offset}`,
    ManagedUserSchema.array(),
  );
}

/** Grant explicit application access to an existing Auth0 identity. */
export function provisionUser(input: ManagedUserInput): Promise<ManagedUser> {
  return requestJson("/users", ManagedUserSchema, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

/** Recheck permissions on the API; hidden browser controls are not authorization. */
export function updateManagedUser(
  id: string,
  role: InternalUserRole,
  isActive: boolean,
  expectedVersion: number,
): Promise<ManagedUser> {
  return requestJson(`/users/${encodeURIComponent(id)}`, ManagedUserSchema, {
    method: "PATCH",
    body: JSON.stringify({
      role,
      is_active: isActive,
      expected_version: expectedVersion,
    }),
  });
}

export function getInvitationDelivery(roleId: string, invitationId: string) {
  return requestJson(
    `/roles/${encodeURIComponent(roleId)}/invites/${encodeURIComponent(invitationId)}/delivery`,
    ProviderInvitationDeliverySchema,
  );
}

export function reissueInvitation(
  roleId: string,
  invitationId: string,
  input: z.infer<typeof InvitationReissueSchema>,
) {
  const body = InvitationReissueSchema.parse(input);
  return requestJson(
    `/roles/${encodeURIComponent(roleId)}/invites/${encodeURIComponent(invitationId)}/reissue`,
    InvitationSchema,
    { method: "POST", body: JSON.stringify(body) },
  );
}
