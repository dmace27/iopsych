"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import {
  ApiClientError,
  generateReport,
  getReport,
  getRole,
  getSubmittedAssessments,
} from "../../lib/api-client";
import type { Report, SubmittedAssessment } from "../../lib/report-contracts";
import { formatDate } from "../../lib/role-ui";
import { EmptyState, ErrorState, LoadingState } from "../ui/workspace-states";
import { ReportDetail } from "./report-detail";

type Failure = { message: string; unauthorized: boolean };
function failure(error: unknown): Failure {
  return {
    message:
      error instanceof ApiClientError
        ? error.message
        : "The report could not be loaded. Try again.",
    unauthorized: error instanceof ApiClientError && error.status === 401,
  };
}
function ReportError({
  error,
  retry,
  returnTo,
}: {
  error: Failure;
  retry: () => void;
  returnTo: string;
}) {
  return (
    <div className="space-y-4">
      <ErrorState
        title="Report unavailable"
        message={error.message}
        onRetry={retry}
      />
      {error.unauthorized ? (
        <Link
          className="inline-block rounded font-bold text-teal-800 underline"
          href={`/sign-in?returnTo=${encodeURIComponent(returnTo)}`}
        >
          Sign in to view reports
        </Link>
      ) : null}
    </div>
  );
}

/** A permalink reads the saved snapshot; it never regenerates scores. */
export function ReportWorkspace({ reportId }: { reportId: string }) {
  return <ReportReader key={reportId} reportId={reportId} />;
}
function ReportReader({ reportId }: { reportId: string }) {
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState<Failure | null>(null);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let alive = true;
    void getReport(reportId)
      .then((value) => {
        if (alive) setReport(value);
      })
      .catch((error) => {
        if (alive) setError(failure(error));
      });
    return () => {
      alive = false;
    };
  }, [reportId, attempt]);
  return (
    <main
      id="main-content"
      className="mx-auto max-w-7xl space-y-8 px-5 py-8 sm:px-8"
    >
      <Link className="rounded font-bold text-teal-800 underline" href="/roles">
        ← Back to roles
      </Link>
      <h1 className="text-3xl font-bold text-slate-950">Recruiter report</h1>
      {error ? (
        <ReportError
          error={error}
          retry={() => {
            setReport(null);
            setError(null);
            setAttempt((value) => value + 1);
          }}
          returnTo={`/reports/${reportId}`}
        />
      ) : report ? (
        <ReportDetail key={report.id} report={report} />
      ) : (
        <LoadingState label="Loading report" />
      )}
    </main>
  );
}

/** Sources are shown chronologically, never ordered by a comparison result. */
export function RecruiterReportsWorkspace({ roleId }: { roleId: string }) {
  return <RoleReports key={roleId} roleId={roleId} />;
}
function RoleReports({ roleId }: { roleId: string }) {
  const [title, setTitle] = useState<string | null>(null);
  const [sources, setSources] = useState<SubmittedAssessment[]>([]);
  const [error, setError] = useState<Failure | null>(null);
  const [actionError, setActionError] = useState<Failure | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [selected, setSelected] = useState<{
    report: Report;
    email: string;
  } | null>(null);
  const lock = useRef(false);
  const retryAction = useRef<() => void>(() => {});
  const generation = useRef(0);
  useEffect(() => {
    const version = generation;
    const current = ++version.current;
    void Promise.all([getRole(roleId), getSubmittedAssessments(roleId)])
      .then(([role, list]) => {
        if (generation.current !== current) return;
        setTitle(role.title);
        setSources(list);
        setHasMore(list.length === 50);
      })
      .catch((error) => {
        if (generation.current === current) setError(failure(error));
      });
    return () => {
      version.current = current + 1;
    };
  }, [roleId, attempt]);
  useEffect(() => {
    if (selected) document.getElementById("report-heading")?.focus();
  }, [selected]);
  async function open(source: SubmittedAssessment) {
    if (lock.current) return;
    retryAction.current = () => {
      void open(source);
    };
    lock.current = true;
    const current = generation.current;
    setBusy(source.assessment_id);
    setActionError(null);
    setSelected(null);
    try {
      const report = source.report_id
        ? await getReport(source.report_id)
        : await generateReport(source);
      if (current !== generation.current) return;
      setSelected({ report, email: source.candidate_email });
      setSources((list) =>
        list.map((item) =>
          item.assessment_id === source.assessment_id
            ? { ...item, report_id: report.id }
            : item,
        ),
      );
    } catch (error) {
      if (current === generation.current) setActionError(failure(error));
    } finally {
      if (current === generation.current) {
        lock.current = false;
        setBusy(null);
      }
    }
  }
  async function more() {
    if (lock.current) return;
    retryAction.current = () => {
      void more();
    };
    lock.current = true;
    const current = generation.current;
    setBusy("more");
    setActionError(null);
    try {
      const list = await getSubmittedAssessments(roleId, sources.length);
      if (current !== generation.current) return;
      setSources((previous) => [...previous, ...list]);
      setHasMore(list.length === 50);
    } catch (error) {
      if (current === generation.current) setActionError(failure(error));
    } finally {
      if (current === generation.current) {
        lock.current = false;
        setBusy(null);
      }
    }
  }
  return (
    <main
      id="main-content"
      className="mx-auto max-w-7xl space-y-8 px-5 py-8 sm:px-8"
    >
      <Link
        className="rounded font-bold text-teal-800 underline"
        href={`/roles/${roleId}`}
      >
        ← Back to role profile
      </Link>
      <header>
        <h1 className="text-3xl font-bold text-slate-950">
          {title ? `${title}: recruiter reports` : "Recruiter reports"}
        </h1>
        <p className="mt-3 max-w-3xl leading-7 text-slate-600">
          Submitted assessments, in submission order. Each report compares six
          separate preferences with the approved role profile used for that
          invitation. There is no overall score or candidate ranking.
        </p>
      </header>
      {error ? (
        <ReportError
          error={error}
          retry={() => {
            setTitle(null);
            setError(null);
            setAttempt((value) => value + 1);
          }}
          returnTo={`/roles/${roleId}/reports`}
        />
      ) : !title ? (
        <LoadingState label="Loading submitted assessments" />
      ) : sources.length === 0 ? (
        <EmptyState
          title="No submitted assessments yet"
          description="Reports become available after a candidate consents and submits an assessment for an approved role profile."
        />
      ) : (
        <section
          aria-labelledby="sources-heading"
          className="rounded-2xl border border-slate-200 bg-white p-6"
        >
          <h2 id="sources-heading" className="text-xl font-bold">
            Submitted assessments
          </h2>
          <ul className="mt-4 divide-y divide-slate-200">
            {sources.map((source) => (
              <li
                key={source.assessment_id}
                className="flex flex-wrap items-center justify-between gap-4 py-5"
              >
                <div className="min-w-0">
                  <h3 className="break-all font-semibold text-slate-950">
                    {source.candidate_email}
                  </h3>
                  <p className="mt-1 text-sm text-slate-600">
                    Profile version {source.role_profile_version} ·{" "}
                    {source.submitted_at
                      ? `Submitted ${formatDate(source.submitted_at)} (UTC)`
                      : "Submission time unavailable"}
                  </p>
                </div>
                <button
                  type="button"
                  disabled={busy !== null}
                  onClick={() => void open(source)}
                  className="min-h-11 rounded-lg border border-teal-700 px-4 py-2 font-bold text-teal-900 disabled:opacity-50 focus-visible:ring-2 focus-visible:ring-teal-700"
                  aria-label={`${source.report_id ? "View" : "Generate"} report for ${source.candidate_email}`}
                >
                  {busy === source.assessment_id
                    ? "Loading report…"
                    : source.report_id
                      ? "View report"
                      : "Generate report"}
                </button>
              </li>
            ))}
          </ul>
          {hasMore ? (
            <button
              type="button"
              disabled={busy !== null}
              onClick={() => void more()}
              className="min-h-11 rounded-lg border border-slate-300 px-4 font-bold disabled:opacity-50 focus-visible:ring-2 focus-visible:ring-teal-700"
            >
              {busy === "more" ? "Loading…" : "Load more assessments"}
            </button>
          ) : null}
        </section>
      )}
      {busy && busy !== "more" ? <LoadingState label="Loading report" /> : null}
      {actionError ? (
        <ReportError
          error={actionError}
          retry={() => retryAction.current()}
          returnTo={`/roles/${roleId}/reports`}
        />
      ) : null}
      {selected ? (
        <div className="space-y-5">
          <Link
            className="rounded font-bold text-teal-800 underline"
            href={`/reports/${selected.report.id}`}
          >
            Open saved report link
          </Link>
          <ReportDetail
            key={selected.report.id}
            report={selected.report}
            candidateEmail={selected.email}
          />
        </div>
      ) : null}
    </main>
  );
}
