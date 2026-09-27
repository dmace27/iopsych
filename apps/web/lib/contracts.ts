import {
  CONSTRUCT_KEYS,
  RoleConstructRatingSchema,
  type RoleConstructRating,
} from "@iopsych/shared";
import { z } from "zod";

/** Internal roles returned by the package 1A current-user endpoint. */
export const InternalUserRoleSchema = z.enum([
  "admin",
  "recruiter",
  "hiring_manager",
]);
export type InternalUserRole = z.infer<typeof InternalUserRoleSchema>;

/** Current internal-user context used only to tailor visible controls. */
export const CurrentUserSchema = z.strictObject({
  id: z.uuid(),
  organization_id: z.uuid(),
  // The backend contract exposes a non-empty string rather than an email type.
  email: z.string().min(1),
  name: z.string().min(1),
  role: InternalUserRoleSchema,
});
export type CurrentUser = z.infer<typeof CurrentUserSchema>;

export const RoleStatusSchema = z.enum(["draft", "active", "archived"]);
export type RoleStatus = z.infer<typeof RoleStatusSchema>;

/** Exact role response returned by the existing package 1B API. */
export const RoleSchema = z.strictObject({
  id: z.uuid(),
  organization_id: z.uuid(),
  title: z.string().min(1),
  department: z.string().min(1),
  location: z.string().min(1),
  job_description: z.string().min(1),
  status: RoleStatusSchema,
  created_at: z.string().min(1),
});
export type Role = z.infer<typeof RoleSchema>;
export const RoleListSchema = z.array(RoleSchema);

export const RoleProfileStatusSchema = z.enum([
  "draft",
  "approved",
  "superseded",
]);
export type RoleProfileStatus = z.infer<typeof RoleProfileStatusSchema>;

/** Complete immutable profile snapshot returned by package 1B. */
export const RoleProfileSchema = z
  .strictObject({
    id: z.uuid(),
    role_id: z.uuid(),
    version: z.int().positive(),
    status: RoleProfileStatusSchema,
    created_by: z.uuid(),
    approved_by: z.uuid().nullable(),
    approved_at: z.string().min(1).nullable(),
    created_at: z.string().min(1),
    constructs: z
      .array(RoleConstructRatingSchema)
      .length(CONSTRUCT_KEYS.length),
  })
  .superRefine((profile, context) => {
    const observed = new Set(profile.constructs.map(({ key }) => key));
    for (const key of CONSTRUCT_KEYS) {
      if (!observed.has(key)) {
        context.addIssue({
          code: "custom",
          message: `Missing construct: ${key}`,
          path: ["constructs"],
        });
      }
    }
  });
export type RoleProfile = z.infer<typeof RoleProfileSchema>;
export const RoleProfileListSchema = z.array(RoleProfileSchema);

export type { RoleConstructRating };

/** Editable role input accepted by POST /v1/roles. */
export type RoleCreateInput = Pick<
  Role,
  "title" | "department" | "location" | "job_description"
>;

/** Complete or partial construct payload accepted by profile POST/PATCH. */
export interface RoleProfileInput {
  constructs: RoleConstructRating[];
}
