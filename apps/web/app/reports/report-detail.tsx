"use client";

import {
  CONSTRUCT_DEFINITIONS_BY_KEY,
  type AlignmentItem,
} from "@iopsych/shared";
import { useEffect, useRef, useState } from "react";

import { ApiClientError } from "../../lib/api-client";
import { getReportTrace } from "../../lib/report-trace-client";
import {
  V1_REPORT_LABELS,
  type ReportTraceV1,
} from "../../lib/report-trace-contracts";
import type { Report } from "../../lib/report-contracts";
import { formatDate } from "../../lib/role-ui";

const classifications = {
  aligned: "Aligned",
  worth_discussing: "Worth discussing",
  potential_friction: "Potential friction",
  insufficient_evidence: "Insufficient evidence",
};
const tones = {
  aligned: "bg-teal-50 text-teal-900 border-teal-200",
  worth_discussing: "bg-sky-50 text-sky-900 border-sky-200",
  potential_friction: "bg-amber-50 text-amber-950 border-amber-200",
  insufficient_evidence: "bg-slate-100 text-slate-800 border-slate-300",
};

function reportLabels(report: Report) {
  return report.result.algorithm_version === "1.0.0"
    ? V1_REPORT_LABELS
    : CONSTRUCT_DEFINITIONS_BY_KEY;
}

/** Six independent, inspectable comparisons and their reviewed question guide. */
export function ReportDetail({
  report,
  candidateEmail,
}: {
  report: Report;
  candidateEmail?: string;
}) {
  const [evidence, setEvidence] = useState<{
    reportId: string;
    constructKey: AlignmentItem["construct_key"];
  } | null>(null);
  const labels = reportLabels(report);
  const selectedEvidence =
    evidence?.reportId === report.id
      ? report.result.items.find(
          (item) => item.construct_key === evidence.constructKey,
        )
      : undefined;
  return (
    <section aria-labelledby="report-heading" className="space-y-6">
      <header className="border-b border-slate-200 pb-4">
        <p className="text-sm font-medium text-slate-600">
          Interview preparation
        </p>
        <h2
          id="report-heading"
          tabIndex={-1}
          className="mt-1 break-words text-2xl font-semibold text-slate-950 focus-visible:outline-2 focus-visible:outline-teal-700"
        >
          {candidateEmail
            ? `Report for ${candidateEmail}`
            : "Construct comparison report"}
        </h2>
        <p className="mt-2 text-sm text-slate-600">
          Approved profile version {report.role_profile_version} · Generated{" "}
          {formatDate(report.generated_at)} (UTC)
        </p>
        <p className="mt-1 text-sm text-slate-600">
          Saved matching algorithm {report.result.algorithm_version}
        </p>
        <a
          href="#interview-guide"
          className="mt-2 inline-flex min-h-11 items-center rounded text-sm font-semibold text-teal-800 underline focus-visible:ring-2 focus-visible:ring-teal-700"
        >
          Jump to interview guide
        </a>
      </header>
      <section aria-labelledby="report-summary-heading">
        <h3
          id="report-summary-heading"
          className="text-lg font-semibold text-slate-950"
        >
          Report summary
        </h3>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-700">
          Six separate working-preference comparisons with the approved role
          profile. Read each interpretation alongside its evidence and
          confidence; there is no overall score or candidate ranking.
        </p>
        <p className="mt-3 border-l-2 border-amber-400 pl-3 text-sm leading-6 text-amber-950">
          {report.usage_warning}
        </p>
      </section>
      <section
        aria-labelledby="supporting-evidence-heading"
        className="surface rounded-lg border border-slate-200 bg-white"
      >
        <h3
          id="supporting-evidence-heading"
          className="border-b border-slate-200 px-4 py-4 text-lg font-semibold"
        >
          Comparisons and supporting evidence
        </h3>
        <div className="divide-y divide-slate-200">
          {report.result.items.map((item) => {
            const definition = labels[item.construct_key];
            const { role, candidate_response: candidate } = item.explanation;
            return (
              <article
                key={item.construct_key}
                aria-labelledby={`construct-${item.construct_key}`}
                className="record-row px-4 py-4 sm:px-5"
              >
                <h4
                  id={`construct-${item.construct_key}`}
                  className="text-base font-semibold text-slate-950"
                >
                  {definition.label}
                </h4>
                <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-2">
                  <p
                    className={`inline-block rounded border px-2 py-1 text-xs font-semibold ${tones[item.classification]}`}
                  >
                    {classifications[item.classification]}
                  </p>
                  <p className="text-sm text-slate-600">
                    {item.confidence.charAt(0).toUpperCase() +
                      item.confidence.slice(1)}{" "}
                    confidence
                  </p>
                </div>
                <dl className="mt-4 grid gap-4 sm:grid-cols-2">
                  <div>
                    <dt className="text-sm font-semibold text-slate-600">
                      {item.construct_key === "structure" &&
                      report.result.algorithm_version !== "1.0.0"
                        ? "Role structure available"
                        : "Role demand"}
                    </dt>
                    <dd className="mt-1 text-base font-semibold text-slate-950">
                      {role.rating}
                      <span className="text-sm font-normal"> / 5</span>
                    </dd>
                    <dd className="mt-1 text-xs leading-5 text-slate-600">
                      {definition.role_prompt}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-sm font-semibold text-slate-600">
                      Candidate response
                    </dt>
                    <dd className="mt-1 text-base font-semibold text-slate-950">
                      {candidate.rating}
                      <span className="text-sm font-normal"> / 5</span>
                    </dd>
                    <dd className="mt-1 text-xs leading-5 text-slate-600">
                      {definition.candidate_prompt}
                    </dd>
                  </div>
                </dl>
                {role.comparison_target === "inverse_role_rating" ? (
                  <p className="mt-4 text-sm leading-6 text-slate-700">
                    Algorithm v1 used an inverse structure comparison: 6 −{" "}
                    {role.rating} = {role.comparison_rating}. The candidate
                    response is compared with {role.comparison_rating}. This
                    historical result is preserved as originally generated.
                  </p>
                ) : item.construct_key === "structure" ? (
                  <p className="mt-4 text-sm leading-6 text-slate-700">
                    Available role structure is compared directly with the
                    candidate’s preference for predictable direction.
                  </p>
                ) : null}
                <p className="mt-4 text-sm leading-6 text-slate-700">
                  <strong>Stored interpretation: </strong>
                  {item.explanation.applied_rule.description}
                </p>
                {item.explanation.uncertainty ? (
                  <p className="mt-3 border-l-2 border-slate-300 pl-3 text-sm leading-6 text-slate-800">
                    <strong>Uncertainty: </strong>
                    {item.explanation.uncertainty}
                  </p>
                ) : null}
                <button
                  type="button"
                  onClick={() =>
                    setEvidence({
                      reportId: report.id,
                      constructKey: item.construct_key,
                    })
                  }
                  className="action-secondary mt-3 min-h-11 rounded-md border border-slate-300 px-3 py-2 text-sm font-semibold text-teal-900 hover:bg-slate-50 focus-visible:ring-2 focus-visible:ring-teal-700 focus-visible:ring-offset-2"
                >
                  View evidence for {definition.label}
                </button>
              </article>
            );
          })}
        </div>
      </section>
      <aside
        aria-label="Responsible use"
        className="border-l-2 border-amber-400 pl-4 text-amber-950"
      >
        <h3 className="text-lg font-semibold">
          Limitations and responsible use
        </h3>
        <p className="mt-2 text-sm leading-6">{report.usage_warning}</p>
        <p className="mt-2 max-w-3xl text-sm leading-6">
          These are six separate working-preference signals, not a diagnosis or
          a prediction of performance. Discuss the evidence, role context, and
          uncertainty with the candidate. “Worth discussing” does not mean “not
          qualified.”
        </p>
      </aside>
      <section
        id="interview-guide"
        aria-labelledby="interview-guide-heading"
        className="surface rounded-lg border border-slate-200 bg-white p-4 sm:p-5"
      >
        <h3
          id="interview-guide-heading"
          className="text-lg font-semibold text-slate-950"
        >
          Interview guide
        </h3>
        <p className="mt-2 text-sm leading-6 text-slate-600">
          Ask open questions, explore examples, and allow the candidate to
          clarify their preferences. Low-confidence signals call for
          clarification.
        </p>
        <ol className="mt-6 space-y-6">
          {report.result.items.map((item) => (
            <li
              key={item.construct_key}
              className="border-t border-slate-200 pt-5"
            >
              <h4 className="font-bold text-slate-950">
                {labels[item.construct_key].label}
              </h4>
              <p className="mt-2 leading-7 text-slate-800">
                {item.interview_questions.primary.text}
              </p>
              <p className="mt-2 text-sm leading-6 text-slate-600">
                <strong>Follow-up: </strong>
                {item.interview_questions.follow_up.text}
              </p>
              <details className="mt-2 text-xs text-slate-600">
                <summary className="min-h-11 cursor-pointer content-center rounded focus-visible:ring-2 focus-visible:ring-teal-700">
                  Question references
                </summary>
                <p className="mt-2 break-all">
                  {item.interview_questions.primary.id}
                  <br />
                  {item.interview_questions.follow_up.id}
                </p>
              </details>
            </li>
          ))}
        </ol>
      </section>
      <details className="border-t border-slate-200 pt-2 text-sm text-slate-600">
        <summary className="min-h-11 cursor-pointer content-center rounded font-semibold focus-visible:ring-2 focus-visible:ring-teal-700">
          Report versions and source references
        </summary>
        <dl className="mt-4 space-y-2 break-all">
          <div>
            <dt className="font-semibold">Assessment definition</dt>
            <dd>
              {report.result.assessment_definition_id} ·{" "}
              {report.result.assessment_definition_version}
            </dd>
          </div>
          <div>
            <dt className="font-semibold">Scoring version</dt>
            <dd>{report.result.scoring_version}</dd>
          </div>
          <div>
            <dt className="font-semibold">Matching version</dt>
            <dd>{report.result.algorithm_version}</dd>
          </div>
          <div>
            <dt className="font-semibold">Assessment record</dt>
            <dd>{report.assessment_id}</dd>
          </div>
          <div>
            <dt className="font-semibold">Role profile record</dt>
            <dd>{report.role_profile_id}</dd>
          </div>
        </dl>
      </details>
      {selectedEvidence ? (
        <EvidenceDrawer
          key={`${report.id}:${selectedEvidence.construct_key}`}
          report={report}
          item={selectedEvidence}
          onDismiss={() => setEvidence(null)}
        />
      ) : null}
    </section>
  );
}

function EvidenceDrawer({
  report,
  item,
  onDismiss,
}: {
  report: Report;
  item: AlignmentItem;
  onDismiss: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    const trigger = document.activeElement as HTMLElement | null;
    dialog?.showModal();
    dialog?.querySelector("button")?.focus();
    return () => {
      dialog?.close();
      trigger?.focus();
    };
  }, []);
  const {
    role,
    candidate_response: candidate,
    applied_rule,
  } = item.explanation;
  return (
    <dialog
      ref={ref}
      aria-labelledby="evidence-heading"
      className="fixed inset-y-0 right-0 m-0 ml-auto h-dvh max-h-none w-full max-w-xl overflow-y-auto overscroll-contain border-l border-slate-200 bg-white p-4 text-slate-800 shadow-xl backdrop:bg-slate-950/40 sm:p-6"
      onCancel={(event) => {
        event.preventDefault();
        onDismiss();
      }}
    >
      <div className="flex items-start justify-between gap-4">
        <h2 id="evidence-heading" className="text-xl font-bold">
          Evidence: {reportLabels(report)[item.construct_key].label}
        </h2>
        <button
          type="button"
          onClick={onDismiss}
          className="action-secondary min-h-11 shrink-0 rounded-md border border-slate-300 px-3 text-sm font-semibold focus-visible:ring-2 focus-visible:ring-teal-700"
        >
          Close evidence
        </button>
      </div>
      <h3 className="mt-8 font-bold">Role rationale</h3>
      <p className="mt-2 leading-7">{role.rationale}</p>
      <h3 className="mt-6 font-bold">Job-description evidence</h3>
      <ul className="mt-3 space-y-3">
        {role.evidence.map((quote, index) => (
          <li key={index}>
            <blockquote className="border-l-4 border-teal-200 pl-4 leading-7">
              {quote}
            </blockquote>
          </li>
        ))}
      </ul>
      <h3 className="mt-6 font-bold">Candidate response summary</h3>
      <p className="mt-2 leading-7">
        {candidate.answered_item_count} of {candidate.assigned_item_count}{" "}
        assigned statements answered; {candidate.skipped_item_count} skipped.
        Raw construct score: {candidate.raw_score}. Response confidence:{" "}
        {candidate.confidence}.
      </p>
      <p className="mt-2 text-sm">
        Candidate confidence describes response completeness, not a probability
        or a prediction of performance.
      </p>
      <ItemEvidence report={report} item={item} />
      <h3 className="mt-6 font-bold">Comparison rule</h3>
      <p className="mt-2 leading-7">
        Comparison target {role.comparison_rating} / 5; candidate response{" "}
        {candidate.rating} / 5. Absolute difference:{" "}
        {applied_rule.absolute_difference}. {applied_rule.description}
      </p>
      <p className="mt-3 text-sm">
        Combined confidence: {item.confidence}. Role evidence confidence:{" "}
        {role.confidence}.
      </p>
      {item.explanation.uncertainty ? (
        <p className="mt-4 rounded-lg bg-slate-100 p-4">
          <strong>Uncertainty: </strong>
          {item.explanation.uncertainty}
        </p>
      ) : null}
    </dialog>
  );
}

function ItemEvidence({
  report,
  item,
}: {
  report: Report;
  item: AlignmentItem;
}) {
  const [attempt, setAttempt] = useState(0);
  return (
    <TraceAttempt
      key={attempt}
      report={report}
      item={item}
      retry={() => setAttempt((value) => value + 1)}
    />
  );
}

function TraceAttempt({
  report,
  item,
  retry,
}: {
  report: Report;
  item: AlignmentItem;
  retry: () => void;
}) {
  const [state, setState] = useState<{
    report?: Report;
    trace?: ReportTraceV1;
    error?: unknown;
  }>({});
  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    void getReportTrace(report, controller.signal)
      .then((trace) => {
        if (active) setState({ report, trace });
      })
      .catch((error: unknown) => {
        if (active) setState({ report, error });
      });
    return () => {
      active = false;
      controller.abort();
    };
  }, [report]);
  const current = state.report === report ? state : {};
  const construct = current.trace?.constructs.find(
    (value) => value.construct_key === item.construct_key,
  );
  if (current.error) {
    const error =
      current.error instanceof ApiClientError ? current.error : null;
    return (
      <section aria-label="Item-level evidence" className="mt-6 space-y-3">
        <p role="status">
          Item-level evidence unavailable for this saved report
        </p>
        {error?.status === 401 ? (
          <a
            className="inline-flex min-h-11 items-center rounded font-semibold underline focus-visible:ring-2 focus-visible:ring-teal-700"
            href={`/sign-in?returnTo=${encodeURIComponent(`/reports/${report.id}`)}`}
          >
            Sign in to view reports
          </a>
        ) : error?.status === 403 || error?.status === 410 ? (
          <p>
            {error.status === 403
              ? "You no longer have access to this evidence."
              : "This candidate’s evidence is no longer available."}
          </p>
        ) : (
          <>
            {error?.status === 404 ? (
              <p>The trace endpoint or saved evidence could not be found.</p>
            ) : null}
            <button
              className="action-secondary min-h-11 rounded border px-3 font-semibold focus-visible:ring-2 focus-visible:ring-teal-700"
              type="button"
              onClick={retry}
            >
              Retry item-level evidence
            </button>
          </>
        )}
      </section>
    );
  }
  if (!construct)
    return (
      <p role="status" className="mt-6">
        Loading item-level evidence…
      </p>
    );
  const choices = {
    most_like: "Most like",
    least_like: "Least like",
    not_selected: "Not selected (answered block)",
    block_skipped: "Block skipped",
  };
  return (
    <section aria-labelledby="item-evidence-heading" className="mt-6">
      <h3 id="item-evidence-heading" className="font-bold">
        Item-level evidence
      </h3>
      <p className="mt-2 text-sm">
        Four historical statements in definition order. Unselected statements
        and skipped blocks both contribute zero; only skipped blocks reduce
        completeness.
      </p>
      <ol className="mt-4 space-y-4">
        {construct.items.map((row) => (
          <li key={row.item_id} className="border-t border-slate-200 py-3">
            <p className="font-semibold">{row.statement}</p>
            <p>
              {choices[row.choice]} · Contribution:{" "}
              {row.contribution > 0 ? "+" : ""}
              {row.contribution}
            </p>
            <p className="break-all text-xs">
              Block {row.block_position}: {row.block_id} · Item: {row.item_id}
            </p>
            {row.choice !== "block_skipped" ? (
              <p className="break-all text-xs">
                Most like: {row.most_like_item_id} · Least like:{" "}
                {row.least_like_item_id}
              </p>
            ) : null}
          </li>
        ))}
      </ol>
      <p className="mt-4">
        Raw total: {item.explanation.candidate_response.raw_score}. Inclusive
        rating band: {construct.rating_threshold.minimum_raw_score} to{" "}
        {construct.rating_threshold.maximum_raw_score} →{" "}
        {construct.rating_threshold.rating} / 5.
      </p>
      <p className="mt-2">
        Completeness: {construct.confidence_rule.level}; skipped statements:{" "}
        {construct.confidence_rule.minimum_skipped_items}
        {construct.confidence_rule.maximum_skipped_items === null
          ? " or more"
          : construct.confidence_rule.maximum_skipped_items ===
              construct.confidence_rule.minimum_skipped_items
            ? ""
            : ` to ${construct.confidence_rule.maximum_skipped_items}`}
        .
      </p>
    </section>
  );
}
