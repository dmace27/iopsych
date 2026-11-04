import { describe, expect, it } from "vitest";

import {
  CandidateDataExportSchema,
  CandidateDeletionSchema,
  PrivacyAuditEventSchema,
  PrivacyStatusSchema,
  PrivacyAssessmentListSchema,
  PrivacyAssessmentLookupSchema,
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

const discoveryPage = {
  schema_version: "1.0",
  items: [
    {
      assessment_id: "80000000-0000-4000-8000-000000000001",
      created_at: "2026-11-04T12:00:00Z",
      submitted_at: "2026-11-04T12:00:00Z",
      retention_expires_at: "2026-12-04T12:00:00Z",
      anonymized_at: null,
    },
  ],
  next_cursor: null,
};

describe("bounded privacy discovery contracts", () => {
  it("accepts the backend page and empty fixture wire shapes", () => {
    expect(PrivacyAssessmentListSchema.parse(discoveryPage)).toEqual(
      discoveryPage,
    );
    expect(
      PrivacyAssessmentListSchema.parse({
        schema_version: "1.0",
        items: [],
        next_cursor: null,
      }),
    ).toMatchObject({ items: [] });
  });
  it("rejects identity fields, oversized pages and malformed lifecycle dates", () => {
    for (const items of [
      [{ ...discoveryPage.items[0], email: "synthetic@example.test" }],
      [{ ...discoveryPage.items[0], created_at: "yesterday" }],
      Array.from({ length: 51 }, () => discoveryPage.items[0]),
    ])
      expect(
        PrivacyAssessmentListSchema.safeParse({ ...discoveryPage, items })
          .success,
      ).toBe(false);
    expect(
      PrivacyAssessmentListSchema.safeParse({
        ...discoveryPage,
        next_cursor: "x".repeat(105),
      }).success,
    ).toBe(false);
  });
  it("requires exactly one UUID filter and bounded pagination", () => {
    for (const query of [
      {},
      { invitation_id: ID, role_id: ID },
      { role_id: "bad" },
      { role_id: ID, limit: 0 },
      { role_id: ID, limit: 51 },
      { role_id: ID, cursor: "x".repeat(105) },
    ]) {
      expect(PrivacyAssessmentLookupSchema.safeParse(query).success).toBe(
        false,
      );
    }
    expect(
      PrivacyAssessmentLookupSchema.safeParse({ invitation_id: ID }).success,
    ).toBe(true);
    expect(
      PrivacyAssessmentLookupSchema.safeParse({
        role_id: ID,
        limit: 50,
        cursor: "opaque",
      }).success,
    ).toBe(true);
  });
});
