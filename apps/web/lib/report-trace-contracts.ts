import {
  AlignmentClassificationSchema,
  CandidateConfidenceRulesSchema,
  CONSTRUCT_KEYS,
  ConstructKeySchema,
  RawScoreThresholdSchema,
  ScoringConfigSchema,
} from "@iopsych/shared";
import { z } from "zod";
import type { Report } from "./report-contracts";

const ItemTraceSchema = z.strictObject({
  block_id: z.string().min(1),
  block_position: z.int().min(1).max(6),
  item_id: z.string().min(1),
  statement: z.string().min(1),
  choice: z.enum(["most_like", "least_like", "not_selected", "block_skipped"]),
  most_like_item_id: z.string().min(1).nullable(),
  least_like_item_id: z.string().min(1).nullable(),
  contribution: z.union([z.literal(-1), z.literal(0), z.literal(1)]),
});
const ConstructTraceSchema = z.strictObject({
  construct_key: ConstructKeySchema,
  items: z.array(ItemTraceSchema).length(4),
  rating_threshold: RawScoreThresholdSchema,
  confidence_rule: z.union([
    CandidateConfidenceRulesSchema.shape.high,
    CandidateConfidenceRulesSchema.shape.medium,
    CandidateConfidenceRulesSchema.shape.low,
  ]),
  question_selection: z.strictObject({
    algorithm_version: z.enum(["1.0.0", "2.0.0"]),
    construct_key: ConstructKeySchema,
    classification: AlignmentClassificationSchema,
    primary_question_id: z.string().min(1),
    follow_up_question_id: z.string().min(1),
  }),
});

export const ReportTraceV1Schema = z
  .strictObject({
    trace_version: z.literal("1.0.0"),
    report_id: z.uuid(),
    assessment_id: z.uuid(),
    role_profile_id: z.uuid(),
    role_profile_version: z.int().positive(),
    algorithm_version: z.enum(["1.0.0", "2.0.0"]),
    assessment_definition_id: z.string().min(1),
    assessment_definition_version: z.string().min(1),
    scoring_version: z.string().min(1),
    definition_sha256: z.string().regex(/^[a-f0-9]{64}$/),
    source: z.literal("stored_assessment"),
    scoring: ScoringConfigSchema,
    constructs: z.array(ConstructTraceSchema).length(6),
  })
  .superRefine((trace, context) => {
    const fail = () =>
      context.addIssue({ code: "custom", message: "Inconsistent saved trace" });
    if (trace.scoring.version !== trace.scoring_version) fail();
    const rows = trace.constructs.flatMap((construct) => construct.items);
    if (new Set(rows.map((row) => row.item_id)).size !== 24) fail();
    trace.constructs.forEach((construct, index) => {
      if (
        construct.construct_key !== CONSTRUCT_KEYS[index] ||
        construct.question_selection.construct_key !== construct.construct_key
      )
        fail();
      if (
        construct.items.some(
          (row, i) =>
            i > 0 &&
            row.block_position <= construct.items[i - 1].block_position,
        )
      )
        fail();
      const raw = construct.items.reduce(
        (total, row) => total + row.contribution,
        0,
      );
      const band = construct.rating_threshold;
      if (
        raw < band.minimum_raw_score ||
        raw > band.maximum_raw_score ||
        !trace.scoring.rating_thresholds.some(
          (threshold) =>
            threshold.rating === band.rating &&
            threshold.minimum_raw_score === band.minimum_raw_score &&
            threshold.maximum_raw_score === band.maximum_raw_score,
        )
      )
        fail();
      const skipped = construct.items.filter(
        (row) => row.choice === "block_skipped",
      ).length;
      const rule = construct.confidence_rule;
      const savedRule = trace.scoring.candidate_confidence[rule.level];
      if (
        skipped < rule.minimum_skipped_items ||
        (rule.maximum_skipped_items !== null &&
          skipped > rule.maximum_skipped_items) ||
        savedRule.minimum_skipped_items !== rule.minimum_skipped_items ||
        savedRule.maximum_skipped_items !== rule.maximum_skipped_items
      )
        fail();
    });
    for (let position = 1; position <= 6; position++) {
      const block = rows.filter((row) => row.block_position === position);
      if (
        block.length !== 4 ||
        new Set(block.map((row) => row.block_id)).size !== 1
      ) {
        fail();
        continue;
      }
      const first = block[0];
      if (
        rows.some(
          (row) =>
            row.block_id === first.block_id && row.block_position !== position,
        )
      )
        fail();
      for (const row of block) {
        if (
          row.most_like_item_id !== first.most_like_item_id ||
          row.least_like_item_id !== first.least_like_item_id
        )
          fail();
        if (row.choice === "block_skipped") {
          if (
            row.most_like_item_id !== null ||
            row.least_like_item_id !== null ||
            row.contribution !== 0
          )
            fail();
        } else {
          if (
            !block.some((item) => item.item_id === row.most_like_item_id) ||
            !block.some((item) => item.item_id === row.least_like_item_id) ||
            row.most_like_item_id === row.least_like_item_id
          )
            fail();
          const choice =
            row.item_id === row.most_like_item_id
              ? "most_like"
              : row.item_id === row.least_like_item_id
                ? "least_like"
                : "not_selected";
          const weight =
            choice === "not_selected"
              ? 0
              : trace.scoring.choice_weights[choice];
          if (row.choice !== choice || row.contribution !== weight) fail();
        }
      }
    }
  });
export type ReportTraceV1 = z.infer<typeof ReportTraceV1Schema>;

export function parseReportTrace(
  payload: unknown,
  report: Report,
): ReportTraceV1 {
  const trace = ReportTraceV1Schema.parse(payload);
  if (
    trace.report_id !== report.id ||
    trace.assessment_id !== report.assessment_id ||
    trace.role_profile_id !== report.role_profile_id ||
    trace.role_profile_version !== report.role_profile_version ||
    trace.algorithm_version !== report.result.algorithm_version ||
    trace.assessment_definition_id !== report.result.assessment_definition_id ||
    trace.assessment_definition_version !==
      report.result.assessment_definition_version ||
    trace.scoring_version !== report.result.scoring_version
  )
    throw new Error("Trace source mismatch");
  for (const construct of trace.constructs) {
    const item = report.result.items.find(
      (item) => item.construct_key === construct.construct_key,
    );
    if (!item) throw new Error("Trace construct mismatch");
    const candidate = item.explanation.candidate_response;
    const skipped = construct.items.filter(
      (row) => row.choice === "block_skipped",
    ).length;
    if (
      candidate.raw_score !==
        construct.items.reduce((total, row) => total + row.contribution, 0) ||
      candidate.rating !== construct.rating_threshold.rating ||
      candidate.confidence !== construct.confidence_rule.level ||
      candidate.assigned_item_count !== 4 ||
      candidate.skipped_item_count !== skipped ||
      candidate.answered_item_count !== 4 - skipped ||
      item.classification !== construct.question_selection.classification ||
      item.interview_questions.primary.id !==
        construct.question_selection.primary_question_id ||
      item.interview_questions.follow_up.id !==
        construct.question_selection.follow_up_question_id
    )
      throw new Error("Trace evidence mismatch");
  }
  return trace;
}

const V1_CONSTRUCT_DEFINITIONS = [
  {
    key: "autonomy",
    label: "Autonomy",
    role_prompt: "How independently the work must be organized",
    candidate_prompt: "How strongly the candidate prefers self-direction",
    comparison_target: "role_rating",
  },
  {
    key: "structure",
    label: "Structure",
    role_prompt: "How defined goals, routines, and requirements are",
    candidate_prompt:
      "How strongly the candidate prefers predictable direction",
    comparison_target: "inverse_role_rating",
  },
  {
    key: "ambiguity",
    label: "Ambiguity tolerance",
    role_prompt: "How often priorities or requirements are unclear or changing",
    candidate_prompt:
      "How comfortable the candidate is acting amid uncertainty",
    comparison_target: "role_rating",
  },
  {
    key: "collaboration",
    label: "Collaboration",
    role_prompt:
      "How much coordination, pairing, and stakeholder work the role needs",
    candidate_prompt: "How much the candidate prefers collaborative work",
    comparison_target: "role_rating",
  },
  {
    key: "mastery",
    label: "Technical mastery",
    role_prompt:
      "How much deep learning and complex problem solving the role offers",
    candidate_prompt:
      "How energizing the candidate finds skill development and hard problems",
    comparison_target: "role_rating",
  },
  {
    key: "pace",
    label: "Pace/context switching",
    role_prompt:
      "How often work requires urgency or shifting between priorities",
    candidate_prompt:
      "How comfortable the candidate is with variety and shifting priorities",
    comparison_target: "role_rating",
  },
] as const;

export const V1_REPORT_LABELS = Object.fromEntries(
  V1_CONSTRUCT_DEFINITIONS.map((definition) => [definition.key, definition]),
) as Record<
  (typeof CONSTRUCT_KEYS)[number],
  (typeof V1_CONSTRUCT_DEFINITIONS)[number]
>;
