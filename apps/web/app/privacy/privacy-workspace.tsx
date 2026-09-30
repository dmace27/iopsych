"use client";

import { useEffect, useMemo, useState } from "react";

import {
  ApiClientError,
  deleteCandidateData,
  exportCandidateData,
  getCurrentUser,
  getPrivacyAuditEvents,
  getPrivacyStatus,
  runPrivacyRetention,
} from "../../lib/api-client";
import type {
  CandidateDataExport,
  CandidateDeletion,
  PrivacyAuditEvent,
  PrivacyStatus,
} from "../../lib/privacy-contracts";
import { ErrorState, LoadingState } from "../ui/workspace-states";

type WorkspaceState =
  | { status: "loading" }
  | { status: "denied" }
  | { status: "error"; message: string }
  | {
      status: "ready";
      privacy: PrivacyStatus;
      auditEvents: PrivacyAuditEvent[];
      auditEntityId: string | null;
      auditHasMore: boolean;
    };

const AUDIT_PAGE_SIZE = 50;

function errorMessage(error: unknown): string {
  if (error instanceof ApiClientError && error.status === 401) {
    return "Your internal session is missing or expired. Sign in again, then retry.";
  }
  return error instanceof Error
    ? error.message
    : "The privacy workspace could not be loaded.";
}

/** Administrator controls for candidate exports, deletion, and retention. */
export function PrivacyWorkspace() {
  const [state, setState] = useState<WorkspaceState>({ status: "loading" });
  const [assessmentId, setAssessmentId] = useState("");
  const [exported, setExported] = useState<CandidateDataExport | null>(null);
  const [deletion, setDeletion] = useState<CandidateDeletion | null>(null);
  const [confirmingDeletion, setConfirmingDeletion] = useState(false);
  const [working, setWorking] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [announcement, setAnnouncement] = useState("");
  const [auditLoadingMore, setAuditLoadingMore] = useState(false);

  async function load(entityId?: string) {
    setState({ status: "loading" });
    try {
      const user = await getCurrentUser();
      if (user.role !== "admin") {
        setState({ status: "denied" });
        return;
      }
      const [privacy, auditEvents] = await Promise.all([
        getPrivacyStatus(),
        getPrivacyAuditEvents(entityId),
      ]);
      setState({
        status: "ready",
        privacy,
        auditEvents,
        auditEntityId: entityId ?? null,
        auditHasMore: auditEvents.length === AUDIT_PAGE_SIZE,
      });
    } catch (error) {
      setState({ status: "error", message: errorMessage(error) });
    }
  }

  useEffect(() => {
    let active = true;
    void getCurrentUser()
      .then(async (user) => {
        if (!active) return;
        if (user.role !== "admin") {
          setState({ status: "denied" });
          return;
        }
        const [privacy, auditEvents] = await Promise.all([
          getPrivacyStatus(),
          getPrivacyAuditEvents(),
        ]);
        if (active) {
          setState({
            status: "ready",
            privacy,
            auditEvents,
            auditEntityId: null,
            auditHasMore: auditEvents.length === AUDIT_PAGE_SIZE,
          });
        }
      })
      .catch((error: unknown) => {
        if (active) setState({ status: "error", message: errorMessage(error) });
      });
    return () => {
      active = false;
    };
  }, []);

  const exportDownload = useMemo(() => {
    if (!exported) return null;
    return `data:application/json;charset=utf-8,${encodeURIComponent(
      JSON.stringify(exported, null, 2),
    )}`;
  }, [exported]);

  async function handleExport() {
    setWorking(true);
    setActionError(null);
    setDeletion(null);
    try {
      const result = await exportCandidateData(assessmentId.trim());
      setExported(result);
      setAnnouncement("Candidate data export created.");
    } catch (error) {
      setActionError(errorMessage(error));
    } finally {
      setWorking(false);
    }
  }

  async function handleDeletion() {
    setWorking(true);
    setActionError(null);
    try {
      const result = await deleteCandidateData(assessmentId.trim());
      setDeletion(result);
      setExported(null);
      setConfirmingDeletion(false);
      setAnnouncement("Candidate data was anonymized.");
      await load(assessmentId.trim());
      setWorking(false);
    } catch (error) {
      setActionError(errorMessage(error));
      setWorking(false);
    }
  }

  async function handleRetention() {
    setWorking(true);
    setActionError(null);
    try {
      const result = await runPrivacyRetention();
      setAnnouncement(
        `Retention run anonymized ${result.anonymized_assessment_ids.length} assessments.`,
      );
      await load();
      setWorking(false);
    } catch (error) {
      setActionError(errorMessage(error));
      setWorking(false);
    }
  }

  async function handleLoadMoreAudit() {
    if (state.status !== "ready" || auditLoadingMore) return;
    setAuditLoadingMore(true);
    setActionError(null);
    try {
      const nextEvents = await getPrivacyAuditEvents(
        state.auditEntityId ?? undefined,
        state.auditEvents.at(-1)?.id,
        AUDIT_PAGE_SIZE,
      );
      setState((current) =>
        current.status === "ready"
          ? {
              ...current,
              auditEvents: [...current.auditEvents, ...nextEvents],
              auditHasMore: nextEvents.length === AUDIT_PAGE_SIZE,
            }
          : current,
      );
      setAnnouncement(`Loaded ${nextEvents.length} additional audit events.`);
    } catch (error) {
      setActionError(errorMessage(error));
    } finally {
      setAuditLoadingMore(false);
    }
  }

  if (state.status === "loading") {
    return (
      <main className="mx-auto max-w-7xl px-5 py-10 sm:px-8" id="main-content">
        <LoadingState label="Loading privacy administration" />
      </main>
    );
  }
  if (state.status === "denied") {
    return (
      <main className="mx-auto max-w-3xl px-5 py-14 sm:px-8" id="main-content">
        <section className="rounded-2xl border border-amber-200 bg-amber-50 p-6">
          <h1 className="text-xl font-bold text-amber-950">
            Administrator access required
          </h1>
          <p className="mt-2 text-sm leading-6 text-amber-900">
            Only organization administrators can export or anonymize candidate
            data.
          </p>
        </section>
      </main>
    );
  }
  if (state.status === "error") {
    return (
      <main className="mx-auto max-w-3xl px-5 py-14 sm:px-8" id="main-content">
        <ErrorState
          message={state.message}
          onRetry={() => void load()}
          title="Privacy administration unavailable"
        />
      </main>
    );
  }

  const validAssessmentId = /^[0-9a-f]{8}-[0-9a-f-]{27}$/i.test(
    assessmentId.trim(),
  );
  return (
    <main className="mx-auto max-w-7xl px-5 py-10 sm:px-8" id="main-content">
      <div aria-live="polite" className="sr-only">
        {announcement}
      </div>
      <header className="border-b border-slate-300 pb-7">
        <p className="text-xs font-bold uppercase tracking-[0.18em] text-teal-800">
          Administrator controls
        </p>
        <h1 className="mt-2 text-4xl font-bold tracking-tight text-slate-950">
          Candidate privacy
        </h1>
        <p className="mt-3 max-w-3xl text-base leading-7 text-slate-600">
          Complete data-rights requests, review immutable activity, and enforce
          the configured pilot retention period.
        </p>
      </header>

      <section aria-labelledby="retention-title" className="mt-8">
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-start">
            <div>
              <h2
                className="text-xl font-bold text-slate-950"
                id="retention-title"
              >
                Retention status
              </h2>
              <p className="mt-2 text-sm text-slate-600">
                Policy window: {state.privacy.retention_days} days
              </p>
              <p className="mt-1 text-sm text-slate-600">
                {state.privacy.next_retention_at
                  ? `Next deadline: ${new Date(
                      state.privacy.next_retention_at,
                    ).toLocaleString("en-CA")}`
                  : "Next deadline: no active assessment deadline"}
              </p>
            </div>
            <button
              className="min-h-11 rounded-xl border border-teal-700 px-5 py-2.5 text-sm font-bold text-teal-800 hover:bg-teal-50 focus-visible:ring-2 focus-visible:ring-teal-700"
              disabled={working}
              onClick={() => void handleRetention()}
              type="button"
            >
              Run retention now
            </button>
          </div>
          <dl className="mt-6 grid gap-4 sm:grid-cols-4">
            {[
              ["Active", state.privacy.active_assessments],
              ["Due", state.privacy.due_assessments],
              ["Anonymized", state.privacy.anonymized_assessments],
              ["Total", state.privacy.total_assessments],
            ].map(([label, value]) => (
              <div className="rounded-xl bg-slate-50 p-4" key={label}>
                <dt className="text-xs font-bold uppercase tracking-wide text-slate-500">
                  {label}
                </dt>
                <dd className="mt-1 text-2xl font-bold text-slate-950">
                  {value}
                </dd>
              </div>
            ))}
          </dl>
        </div>
      </section>

      <section
        aria-labelledby="rights-title"
        className="mt-8 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm"
      >
        <h2 className="text-xl font-bold text-slate-950" id="rights-title">
          Complete a data-rights request
        </h2>
        <label className="mt-5 block max-w-2xl text-sm font-bold text-slate-800">
          Assessment ID
          <input
            className="field-control mt-2 font-mono"
            onChange={(event) => {
              setAssessmentId(event.target.value);
              setConfirmingDeletion(false);
              setActionError(null);
            }}
            placeholder="00000000-0000-4000-8000-000000000000"
            value={assessmentId}
          />
        </label>
        <div className="mt-4 flex flex-wrap gap-3">
          <button
            className="min-h-11 rounded-xl bg-teal-800 px-5 py-2.5 text-sm font-bold text-white disabled:opacity-50"
            disabled={!validAssessmentId || working}
            onClick={() => void handleExport()}
            type="button"
          >
            Create JSON export
          </button>
          <button
            className="min-h-11 rounded-xl border border-rose-700 px-5 py-2.5 text-sm font-bold text-rose-800 disabled:opacity-50"
            disabled={!validAssessmentId || working}
            onClick={() => setConfirmingDeletion(true)}
            type="button"
          >
            Prepare anonymization
          </button>
          <button
            className="min-h-11 rounded-xl border border-slate-400 px-5 py-2.5 text-sm font-bold text-slate-700 disabled:opacity-50"
            disabled={!validAssessmentId || working}
            onClick={() => void load(assessmentId.trim())}
            type="button"
          >
            Look up audit history
          </button>
        </div>
        {confirmingDeletion ? (
          <div className="mt-5 rounded-xl border border-rose-200 bg-rose-50 p-4">
            <p className="text-sm leading-6 text-rose-950">
              This revokes candidate access, erases assessment payloads, and
              deletes derived reports. Immutable audit tombstones remain.
            </p>
            <button
              className="mt-3 min-h-11 rounded-xl bg-rose-800 px-5 py-2.5 text-sm font-bold text-white"
              disabled={working}
              onClick={() => void handleDeletion()}
              type="button"
            >
              Confirm anonymization
            </button>
          </div>
        ) : null}
        {actionError ? (
          <p className="mt-4 text-sm font-semibold text-rose-800" role="alert">
            {actionError}
          </p>
        ) : null}
        {deletion ? (
          <p className="mt-4 rounded-xl bg-emerald-50 p-4 text-sm text-emerald-950">
            Assessment {deletion.assessment_id} was anonymized. Derived reports
            removed: {deletion.reports_deleted}.
          </p>
        ) : null}
        {exported && exportDownload ? (
          <div className="mt-5 rounded-xl border border-teal-200 bg-teal-50 p-4">
            <p className="text-sm font-bold text-teal-950">
              Export ready for {exported.invitation.email}
            </p>
            <a
              className="mt-3 inline-block font-bold text-teal-800 underline"
              download={`candidate-data-${exported.assessment.id}.json`}
              href={exportDownload}
            >
              Download JSON export
            </a>
          </div>
        ) : null}
      </section>

      <section aria-labelledby="audit-title" className="mt-8">
        <h2 className="text-xl font-bold text-slate-950" id="audit-title">
          Immutable audit history
        </h2>
        {state.auditEvents.length === 0 ? (
          <p className="mt-4 rounded-xl border border-slate-200 bg-white p-5 text-sm text-slate-600">
            No matching audit events.
          </p>
        ) : (
          <ul className="mt-4 space-y-3">
            {state.auditEvents.map((event) => (
              <li
                className="rounded-xl border border-slate-200 bg-white p-4"
                key={event.id}
              >
                <p className="font-bold text-slate-900">{event.event_type}</p>
                <p className="mt-1 break-all font-mono text-xs text-slate-500">
                  {event.entity_type} · {event.entity_id}
                </p>
                <p className="mt-1 text-xs text-slate-500">
                  {new Date(event.occurred_at).toLocaleString("en-CA")}
                </p>
                <p className="mt-2 break-all text-xs text-slate-600">
                  Actor: {event.actor_id ?? "system"}
                </p>
                <pre className="mt-2 overflow-x-auto rounded-lg bg-slate-50 p-3 text-xs text-slate-700">
                  {JSON.stringify(event.details, null, 2)}
                </pre>
              </li>
            ))}
          </ul>
        )}
        {state.auditHasMore ? (
          <button
            className="mt-4 min-h-11 rounded-xl border border-slate-400 px-5 py-2.5 text-sm font-bold text-slate-700 disabled:opacity-50"
            disabled={auditLoadingMore || working}
            onClick={() => void handleLoadMoreAudit()}
            type="button"
          >
            {auditLoadingMore
              ? "Loading audit history…"
              : "Load more audit history"}
          </button>
        ) : null}
      </section>
    </main>
  );
}
