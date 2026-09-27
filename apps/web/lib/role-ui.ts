import { CONSTRUCT_KEYS } from "@iopsych/shared";

import type {
  InternalUserRole,
  RoleConstructRating,
  RoleProfile,
} from "./contracts";

/** Return role-authoring capability while FastAPI remains authoritative. */
export function canEditRoles(role: InternalUserRole): boolean {
  return role === "recruiter" || role === "admin";
}

/** Recruiters and explicit administrators may create complete profile drafts. */
export function canCreateProfiles(role: InternalUserRole): boolean {
  return role === "recruiter" || role === "admin";
}

/** Every internal role may revise the latest draft before manager approval. */
export function canEditProfiles(role: InternalUserRole): boolean {
  return role === "recruiter" || role === "hiring_manager" || role === "admin";
}

/** Hiring-manager approval is intentionally exclusive. */
export function canApproveProfiles(role: InternalUserRole): boolean {
  return role === "hiring_manager";
}

/** Format API timestamps consistently for visible and assistive output. */
export function formatDate(value: string): string {
  return new Intl.DateTimeFormat("en-CA", {
    day: "numeric",
    month: "short",
    timeZone: "UTC",
    year: "numeric",
  }).format(new Date(value));
}

/** Keep version history stable without mutating data returned by the API. */
export function sortProfiles(profiles: RoleProfile[]): RoleProfile[] {
  return [...profiles].sort((left, right) => left.version - right.version);
}

/** Build a neutral blank draft without pretending an extraction occurred. */
export function blankConstructs(): RoleConstructRating[] {
  return CONSTRUCT_KEYS.map((key) => ({
    key,
    rating: 3,
    confidence: "medium",
    rationale: "",
    evidence: [""],
  }));
}
