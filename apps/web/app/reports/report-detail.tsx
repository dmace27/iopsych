"use client";

import {
  CONSTRUCT_DEFINITIONS_BY_KEY,
  type AlignmentItem,
} from "@iopsych/shared";
import { useEffect, useRef, useState } from "react";

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

/** Six independent, inspectable comparisons and their reviewed question guide. */
export function ReportDetail({
  report,
  candidateEmail,
}: {
  report: Report;
  candidateEmail?: string;
}) {
  const [evidence, setEvidence] = useState<AlignmentItem | null>(null);
  return (
    <section aria-labelledby="report-heading" className="space-y-8">
      <header>
        <p className="text-xs font-bold uppercase tracking-widest text-teal-800">
          Interview preparation
        </p>
        <h2
          id="report-heading"
          tabIndex={-1}
          className="mt-2 break-words text-2xl font-bold text-slate-950"
        >
          {candidateEmail
            ? `Report for ${candidateEmail}`
            : "Construct comparison report"}
        </h2>
        <p className="mt-2 text-sm text-slate-600">
          Approved profile version {report.role_profile_version} · Generated{" "}
          {formatDate(report.generated_at)} (UTC)
        </p>
        <a
          href="#interview-guide"
          className="mt-3 inline-block rounded font-semibold text-teal-800 underline focus-visible:ring-2 focus-visible:ring-teal-700"
        >
          Jump to interview guide
        </a>
      </header>
      <aside
        aria-label="Responsible use"
        className="rounded-2xl border border-amber-200 bg-amber-50 p-5 text-amber-950"
      >
        <h3 className="font-bold">Use this report to prepare a conversation</h3>
        <p className="mt-2 text-sm leading-6">{report.usage_warning}</p>
        <p className="mt-2 text-sm leading-6">
          These are six separate working-preference signals, not a diagnosis or
          a prediction of performance. Discuss the evidence, role context, and
          uncertainty with the candidate. “Worth discussing” does not mean “not
          qualified.”
        </p>
      </aside>
      <div className="grid gap-5 md:grid-cols-2">
        {report.result.items.map((item) => {
          const definition = CONSTRUCT_DEFINITIONS_BY_KEY[item.construct_key];
          const { role, candidate_response: candidate } = item.explanation;
          return (
            <article
              key={item.construct_key}
              aria-labelledby={`construct-${item.construct_key}`}
              className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm"
            >
              <h3
                id={`construct-${item.construct_key}`}
                className="text-xl font-bold text-slate-950"
              >
                {definition.label}
              </h3>
              <p
                className={`mt-3 inline-block rounded-full border px-3 py-1 text-sm font-semibold ${tones[item.classification]}`}
              >
                {classifications[item.classification]}
              </p>
              <p className="mt-3 text-sm font-semibold text-slate-700">
                {item.confidence.charAt(0).toUpperCase() +
                  item.confidence.slice(1)}{" "}
                confidence
              </p>
              <dl className="mt-5 grid grid-cols-2 gap-4">
                <div>
                  <dt className="text-sm font-semibold text-slate-600">
                    Role demand
                  </dt>
                  <dd className="mt-1 text-2xl font-bold text-slate-950">
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
                  <dd className="mt-1 text-2xl font-bold text-slate-950">
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
                  Structure uses an inverse comparison: 6 − {role.rating} ={" "}
                  {role.comparison_rating}. The candidate response is compared
                  with {role.comparison_rating}, rather than the role demand
                  shown above.
                </p>
              ) : null}
              <p className="mt-4 text-sm leading-6 text-slate-700">
                {item.explanation.applied_rule.description}
              </p>
              {item.explanation.uncertainty ? (
                <p className="mt-3 rounded-lg bg-slate-100 p-3 text-sm leading-6 text-slate-800">
                  <strong>Uncertainty: </strong>
                  {item.explanation.uncertainty}
                </p>
              ) : null}
              <button
                type="button"
                onClick={() => setEvidence(item)}
                className="mt-5 min-h-11 rounded-lg border border-teal-700 px-4 py-2 font-semibold text-teal-900 hover:bg-teal-50 focus-visible:ring-2 focus-visible:ring-teal-700 focus-visible:ring-offset-2"
              >
                View evidence for {definition.label}
              </button>
            </article>
          );
        })}
      </div>
      <section
        id="interview-guide"
        aria-labelledby="interview-guide-heading"
        className="rounded-2xl border border-slate-200 bg-white p-6"
      >
        <h3
          id="interview-guide-heading"
          className="text-xl font-bold text-slate-950"
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
                {CONSTRUCT_DEFINITIONS_BY_KEY[item.construct_key].label}
              </h4>
              <p className="mt-2 leading-7 text-slate-800">
                {item.interview_questions.primary.text}
              </p>
              <p className="mt-2 text-sm leading-6 text-slate-600">
                <strong>Follow-up: </strong>
                {item.interview_questions.follow_up.text}
              </p>
              <details className="mt-2 text-xs text-slate-600">
                <summary className="cursor-pointer rounded focus-visible:ring-2 focus-visible:ring-teal-700">
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
      <details className="rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-600">
        <summary className="cursor-pointer rounded font-semibold focus-visible:ring-2 focus-visible:ring-teal-700">
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
      {evidence ? (
        <EvidenceDrawer item={evidence} onDismiss={() => setEvidence(null)} />
      ) : null}
    </section>
  );
}

function EvidenceDrawer({
  item,
  onDismiss,
}: {
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
      className="fixed inset-y-0 right-0 m-0 ml-auto h-dvh max-h-none w-full max-w-xl overflow-y-auto border-l border-slate-200 bg-white p-6 text-slate-800 shadow-xl backdrop:bg-slate-950/50 sm:p-8"
      onCancel={(event) => {
        event.preventDefault();
        onDismiss();
      }}
    >
      <div className="flex items-start justify-between gap-4">
        <h2 id="evidence-heading" className="text-xl font-bold">
          Evidence: {CONSTRUCT_DEFINITIONS_BY_KEY[item.construct_key].label}
        </h2>
        <button
          type="button"
          onClick={onDismiss}
          className="min-h-11 rounded-lg border border-slate-300 px-3 font-bold focus-visible:ring-2 focus-visible:ring-teal-700"
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
