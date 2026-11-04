import { z } from "zod";
import type { InternalUserRole } from "./contracts";

const shortText = z.string().trim().min(1).max(160);
export const RoleUpdateSchema = z
  .strictObject({
    title: shortText.optional(),
    department: shortText.optional(),
    location: shortText.optional(),
    job_description: z.string().trim().min(1).max(100_000).optional(),
  })
  .refine(
    (value) => Object.values(value).some((field) => field !== undefined),
    {
      message: "Change at least one role field before saving.",
    },
  );
export type RoleUpdateInput = z.infer<typeof RoleUpdateSchema>;
export function canMaintainRole(role: InternalUserRole): boolean {
  return role === "admin" || role === "recruiter";
}
