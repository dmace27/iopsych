import { describe, expect, it } from "vitest";

import {
  CandidateDataExportSchema,
  CandidateDeletionSchema,
  PrivacyAuditEventSchema,
  PrivacyStatusSchema,
  RetentionRunSchema,
} from "./privacy-contracts";

const ID = "11111111-1111-4111-8111-111111111111";

describe("privacy response contracts", () => {
  it("accepts complete bounded privacy responses", () => {
    expect(
      PrivacyStatusSchema.parse({
        active_assessments: 1,
        anonymized_assessments: 2,
        due_assessments: 0,
        next_retention_at: null,
        retention_days: 90,
        total_assessments: 3,
      }),
    ).toMatchObject({ retention_days: 90 });
    expect(
      CandidateDeletionSchema.parse({
        already_anonymized: false,
        anonymized_at: "2026-09-29T12:00:00Z",
        assessment_id: ID,
        reports_deleted: 0,
      }),
    ).toMatchObject({ assessment_id: ID });
    expect(
      RetentionRunSchema.parse({
        anonymized_assessment_ids: [ID],
        completed_at: "2026-09-29T12:00:00Z",
      }),
    ).toMatchObject({ anonymized_assessment_ids: [ID] });
  });

  it("rejects malformed, negative, and extra fields", () => {
    expect(
      PrivacyStatusSchema.safeParse({
        active_assessments: -1,
        anonymized_assessments: 0,
        due_assessments: 0,
        next_retention_at: null,
        retention_days: 0,
        total_assessments: 0,
      }).success,
    ).toBe(false);
    expect(
      PrivacyAuditEventSchema.safeParse({
        actor_id: null,
        details: {},
        entity_id: ID,
        entity_type: "assessment",
        event_type: "candidate_data.exported",
        extra: true,
        id: ID,
        occurred_at: "2026-09-29T12:00:00Z",
      }).success,
    ).toBe(false);
    expect(
      CandidateDataExportSchema.safeParse({ schema_version: "2.0" }).success,
    ).toBe(false);
  });
});
