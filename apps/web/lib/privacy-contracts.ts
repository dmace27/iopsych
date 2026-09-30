import { z } from "zod";

const JsonObjectSchema = z.record(z.string(), z.unknown());

export const PrivacyStatusSchema = z.strictObject({
  retention_days: z.int().positive(),
  total_assessments: z.int().nonnegative(),
  active_assessments: z.int().nonnegative(),
  anonymized_assessments: z.int().nonnegative(),
  due_assessments: z.int().nonnegative(),
  next_retention_at: z.string().min(1).nullable(),
});
export type PrivacyStatus = z.infer<typeof PrivacyStatusSchema>;

export const PrivacyAuditEventSchema = z.strictObject({
  id: z.uuid(),
  actor_id: z.uuid().nullable(),
  event_type: z.string().min(1),
  entity_type: z.string().min(1),
  entity_id: z.uuid(),
  occurred_at: z.string().min(1),
  details: JsonObjectSchema,
});
export const PrivacyAuditEventListSchema = z.array(PrivacyAuditEventSchema);
export type PrivacyAuditEvent = z.infer<typeof PrivacyAuditEventSchema>;

export const CandidateDeletionSchema = z.strictObject({
  assessment_id: z.uuid(),
  anonymized_at: z.string().min(1),
  already_anonymized: z.boolean(),
  reports_deleted: z.int().nonnegative(),
});
export type CandidateDeletion = z.infer<typeof CandidateDeletionSchema>;

export const RetentionRunSchema = z.strictObject({
  completed_at: z.string().min(1),
  anonymized_assessment_ids: z.array(z.uuid()),
});
export type RetentionRun = z.infer<typeof RetentionRunSchema>;

export const CandidateDataExportSchema = z.strictObject({
  schema_version: z.literal("1.0"),
  generated_at: z.string().min(1),
  organization: z.strictObject({
    name: z.string().min(1),
    role_title: z.string().min(1),
    role_profile_version: z.int().positive(),
  }),
  invitation: z.strictObject({
    id: z.uuid(),
    email: z.email(),
    status: z.enum([
      "pending_delivery",
      "active",
      "consented",
      "declined",
      "revoked",
      "expired",
    ]),
    created_at: z.string().min(1),
    sent_at: z.string().min(1).nullable(),
    expires_at: z.string().min(1),
    revoked_at: z.string().min(1).nullable(),
  }),
  consent: z.strictObject({
    id: z.uuid(),
    decision: z.enum(["consent", "decline"]),
    notice_version: z.string().min(1),
    recorded_at: z.string().min(1),
  }),
  assessment: z.strictObject({
    id: z.uuid(),
    created_at: z.string().min(1),
    submitted_at: z.string().min(1).nullable(),
    retention_expires_at: z.string().min(1).nullable(),
    definition: JsonObjectSchema,
    responses: JsonObjectSchema,
    scores: JsonObjectSchema,
  }),
  reports: z.array(
    z.strictObject({
      id: z.uuid(),
      generated_at: z.string().min(1),
      algorithm_version: z.string().min(1),
      result: JsonObjectSchema,
    }),
  ),
  activity: z.array(
    z.strictObject({
      event_type: z.string().min(1),
      entity_type: z.string().min(1),
      entity_id: z.uuid(),
      occurred_at: z.string().min(1),
      details: JsonObjectSchema,
    }),
  ),
});
export type CandidateDataExport = z.infer<typeof CandidateDataExportSchema>;
