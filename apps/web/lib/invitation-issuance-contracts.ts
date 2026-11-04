import { z } from "zod";

export const InvitationCreateSchema = z.strictObject({
  role_profile_id: z.uuid(),
  email: z
    .string()
    .trim()
    .min(3)
    .max(320)
    .regex(/^[^@\s]+@[^@\s]+\.[^@\s]+$/),
  expires_in_hours: z.int().min(1).max(720).nullable().optional(),
});
export type InvitationCreate = z.infer<typeof InvitationCreateSchema>;
