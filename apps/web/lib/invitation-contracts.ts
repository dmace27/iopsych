import { z } from "zod";
import type { InternalUserRole } from "./contracts";

export const InvitationSchema = z.strictObject({
  id: z.uuid(),
  role_profile_id: z.uuid(),
  email: z.string().min(1),
  expires_at: z.iso.datetime({ offset: true }),
  status: z.enum([
    "pending_delivery",
    "active",
    "consented",
    "declined",
    "revoked",
    "expired",
  ]),
  delivery_state: z
    .enum(["queued", "sending", "sent", "uncertain", "cancelled", "expired"])
    .nullable()
    .optional(),
  sent_at: z.iso.datetime({ offset: true }).nullable(),
  revoked_at: z.iso.datetime({ offset: true }).nullable(),
  created_at: z.iso.datetime({ offset: true }),
});
export const InvitationListSchema = z.strictObject({
  items: z.array(InvitationSchema).max(100),
  next_cursor: z.string().min(1).nullable(),
});
export type Invitation = z.infer<typeof InvitationSchema>;
export type InvitationList = z.infer<typeof InvitationListSchema>;
export function canManageInvitations(role: InternalUserRole): boolean {
  return role === "admin" || role === "recruiter";
}

export const ProviderInvitationDeliverySchema = z.strictObject({
  id: z.uuid(),
  invite_id: z.uuid(),
  status: z.enum([
    "queued",
    "retrying",
    "sent",
    "delivered",
    "failed",
    "bounced",
    "complained",
    "reissue_required",
    "cancelled",
  ]),
  attempt_count: z.number().int().nonnegative(),
  next_attempt_at: z.iso.datetime({ offset: true }),
  retry_until: z.iso.datetime({ offset: true }),
  last_error_code: z.string().nullable(),
});
export type ProviderInvitationDelivery = z.infer<
  typeof ProviderInvitationDeliverySchema
>;
export const InvitationReissueSchema = z.strictObject({
  request_id: z.uuid(),
  expires_in_hours: z.number().int().min(1).max(720).optional(),
});
