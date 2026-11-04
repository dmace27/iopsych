"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import {
  ApiClientError,
  deleteCandidateData,
  exportCandidateData,
  getCurrentUser,
  getPrivacyAuditEvents,
  getPrivacyStatus,
  getPrivacyAssessments,
  runPrivacyRetention,
} from "../../lib/api-client";
import type {
  CandidateDataExport,
  CandidateDeletion,
  PrivacyAuditEvent,
  PrivacyStatus,
  PrivacyAssessmentList,
  PrivacyAssessmentLookup,
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
      auditAssessmentId: string | null;
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
  const [lookupKind, setLookupKind] = useState<"invitation_id" | "role_id">(
    "invitation_id",
  );
  const [lookupReference, setLookupReference] = useState("");
  const [lookupResult, setLookupResult] =
    useState<PrivacyAssessmentList | null>(null);
  const [lookupQuery, setLookupQuery] =
    useState<PrivacyAssessmentLookup | null>(null);
  const [anonymizationConfirmations, setAnonymizationConfirmations] = useState<
    ReadonlyMap<string, string>
  >(new Map());
  const [lookupLoading, setLookupLoading] = useState(false);
  const [lookupError, setLookupError] = useState<string | null>(null);
  const auditRequestVersion = useRef(0);
  const [auditLoadingMore, setAuditLoadingMore] = useState(false);

  function invalidateAuditCallbacks() {
    auditRequestVersion.current += 1;
    setAuditLoadingMore(false);
  }

  function selectAssessment(id: string) {
    setAssessmentId(id);
    setConfirmingDeletion(false);
    setExported(null);
    setDeletion(null);
    setActionError(null);
    setAnnouncement(id ? `Selected assessment ${id}.` : "");
  }

  function resetLookup() {
    setLookupResult(null);
    setLookupQuery(null);
    setLookupError(null);
    selectAssessment("");
  }

  async function handleLookup(nextPage = false) {
    if (lookupLoading || working) return;
    invalidateAuditCallbacks();
    const query: PrivacyAssessmentLookup =
      nextPage && lookupQuery && lookupResult?.next_cursor
        ? { ...lookupQuery, cursor: lookupResult.next_cursor }
        : lookupKind === "invitation_id"
          ? { invitation_id: lookupReference.trim(), limit: 20 }
          : { role_id: lookupReference.trim(), limit: 20 };
    setLookupLoading(true);
    setLookupError(null);
    selectAssessment("");
    try {
      const result = await getPrivacyAssessments(query);
      setLookupQuery(query);
      setLookupResult(result);
      setAnnouncement(`Found ${result.items.length} assessments on this page.`);
    } catch (error) {
      setLookupError(errorMessage(error));
    } finally {
      setLookupLoading(false);
    }
  }

  async function load(relatedAssessmentId?: string, afterMutation = false) {
    invalidateAuditCallbacks();
    if (!afterMutation) setState({ status: "loading" });
    try {
      const user = await getCurrentUser();
      if (user.role !== "admin") {
        setState({ status: "denied" });
        return;
      }
      const [privacy, auditEvents] = await Promise.all([
        getPrivacyStatus(),
        getPrivacyAuditEvents(
          relatedAssessmentId
            ? { assessment_id: relatedAssessmentId }
            : undefined,
        ),
      ]);
      setState({
        status: "ready",
        privacy,
        auditEvents,
        auditAssessmentId: relatedAssessmentId ?? null,
        auditHasMore: auditEvents.length === AUDIT_PAGE_SIZE,
      });
    } catch (error) {
      if (afterMutation) {
        setActionError(
          `The operation completed, but privacy status and audit history could not be refreshed. ${errorMessage(error)}`,
        );
      } else {
        setState({ status: "error", message: errorMessage(error) });
      }
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
            auditAssessmentId: null,
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
    invalidateAuditCallbacks();
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
    invalidateAuditCallbacks();
    setWorking(true);
    setActionError(null);
    try {
      const result = await deleteCandidateData(assessmentId.trim());
      setAnonymizationConfirmations((current) =>
        new Map(current).set(result.assessment_id, result.anonymized_at),
      );
      setDeletion(result);
      setExported(null);
      setConfirmingDeletion(false);
      setAnnouncement("Candidate data was anonymized.");
      await load(assessmentId.trim(), true);
      setWorking(false);
    } catch (error) {
      setActionError(errorMessage(error));
      setWorking(false);
    }
  }

  async function handleRetention() {
    invalidateAuditCallbacks();
    setWorking(true);
    setActionError(null);
    try {
      const result = await runPrivacyRetention();
      setAnonymizationConfirmations((current) => {
        const next = new Map(current);
        for (const id of result.anonymized_assessment_ids) {
          if (!next.has(id)) next.set(id, "Yes (confirmed by retention)");
        }
        return next;
      });
      if (result.anonymized_assessment_ids.includes(assessmentId.trim())) {
        setExported(null);
        setConfirmingDeletion(false);
      }
      setAnnouncement(
        `Retention run anonymized ${result.anonymized_assessment_ids.length} assessments.`,
      );
      await load(undefined, true);
      setWorking(false);
    } catch (error) {
      setActionError(errorMessage(error));
      setWorking(false);
    }
  }

  async function handleLoadMoreAudit() {
    if (
      state.status !== "ready" ||
      auditLoadingMore ||
      lookupLoading ||
      working
    )
      return;
    const requestVersion = ++auditRequestVersion.current;
    setAuditLoadingMore(true);
    setActionError(null);
    try {
      const nextEvents = await getPrivacyAuditEvents(
        state.auditAssessmentId
          ? { assessment_id: state.auditAssessmentId }
          : undefined,
        state.auditEvents.at(-1)?.id,
        AUDIT_PAGE_SIZE,
      );
      if (requestVersion !== auditRequestVersion.current) return;
      setState((current) =>
        current.status === "ready" && current.auditEvents === state.auditEvents
          ? {
              ...current,
              auditEvents: [...current.auditEvents, ...nextEvents],
              auditHasMore: nextEvents.length === AUDIT_PAGE_SIZE,
            }
          : current,
      );
      setAnnouncement(`Loaded ${nextEvents.length} additional audit events.`);
    } catch (error) {
      if (requestVersion === auditRequestVersion.current) {
        setActionError(errorMessage(error));
      }
    } finally {
      if (requestVersion === auditRequestVersion.current) {
        setAuditLoadingMore(false);
      }
    }
  }

  if (state.status === "loading") {
    return (
      <main
        className="workspace-shell mx-auto max-w-6xl px-5 py-8 sm:px-8"
        id="main-content"
      >
        <LoadingState label="Loading privacy administration" />
      </main>
    );
  }
  if (state.status === "denied") {
    return (
      <main className="mx-auto max-w-3xl px-5 py-14 sm:px-8" id="main-content">
        <section className="border-l-4 border-amber-600 bg-white p-4">
          <h1 className="workspace-title text-2xl font-semibold text-amber-950">
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
    <main
      className="workspace-shell mx-auto max-w-6xl px-5 py-8 text-slate-900 sm:px-8"
      id="main-content"
    >
      <div aria-live="polite" className="sr-only">
        {announcement}
      </div>
      <header className="border-b border-slate-200 pb-5">
        <h1 className="workspace-title text-2xl font-semibold text-slate-950">
          Candidate privacy
        </h1>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
          Complete data-rights requests, review immutable activity, and enforce
          the configured pilot retention period.
        </p>
      </header>

      <section aria-labelledby="retention-title" className="mt-6">
        <div className="surface border-b border-slate-200 bg-white p-4">
          <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-start">
            <div>
              <h2
                className="text-lg font-semibold text-slate-950"
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
              className="action-secondary min-h-11 rounded-md border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 focus-visible:ring-2 focus-visible:ring-teal-700"
              disabled={working || lookupLoading}
              onClick={() => void handleRetention()}
              type="button"
            >
              Run retention now
            </button>
          </div>
          <dl className="mt-4 grid grid-cols-2 gap-4 border-t border-slate-200 pt-4 sm:grid-cols-4">
            {[
              ["Active", state.privacy.active_assessments],
              ["Due", state.privacy.due_assessments],
              ["Anonymized", state.privacy.anonymized_assessments],
              ["Total", state.privacy.total_assessments],
            ].map(([label, value]) => (
              <div key={label}>
                <dt className="text-sm text-slate-600">{label}</dt>
                <dd className="mt-1 text-xl font-semibold text-slate-950">
                  {value}
                </dd>
              </div>
            ))}
          </dl>
        </div>
      </section>

      <section
        aria-labelledby="lookup-title"
        className="surface mt-6 border-b border-slate-200 bg-white p-4"
      >
        <h2 id="lookup-title" className="text-lg font-semibold text-slate-950">
          Find an assessment
        </h2>
        <p className="mt-2 text-sm text-slate-600">
          Use an invitation or role reference from your organization. Results
          contain assessment references and lifecycle dates only, with up to 20
          results per page.
        </p>
        <form
          className="grid gap-x-4 sm:grid-cols-[minmax(10rem,1fr)_minmax(0,2fr)]"
          onSubmit={(event) => {
            event.preventDefault();
            void handleLookup();
          }}
        >
          <label className="field-label mt-4 block min-w-0 text-sm font-medium">
            Reference type
            <select
              className="field-control mt-2 min-h-11"
              value={lookupKind}
              disabled={lookupLoading || working}
              onChange={(event) => {
                setLookupKind(event.target.value as typeof lookupKind);
                resetLookup();
              }}
            >
              <option value="invitation_id">Invitation ID</option>
              <option value="role_id">Role ID</option>
            </select>
          </label>
          <label className="field-label mt-4 block min-w-0 text-sm font-medium">
            Reference ID
            <input
              className="field-control mt-2 min-h-11 font-mono"
              value={lookupReference}
              disabled={lookupLoading || working}
              onChange={(event) => {
                setLookupReference(event.target.value);
                resetLookup();
              }}
              placeholder="00000000-0000-4000-8000-000000000000"
            />
          </label>
          <button
            className="action-primary mt-4 min-h-11 justify-self-start rounded-md bg-teal-700 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-700"
            disabled={
              lookupLoading ||
              working ||
              !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(
                lookupReference.trim(),
              )
            }
            type="submit"
          >
            Find assessments
          </button>
        </form>
        {lookupLoading ? (
          <p role="status" className="mt-4">
            Finding assessments…
          </p>
        ) : null}
        {lookupError ? (
          <p role="alert" className="mt-4 text-rose-800">
            {lookupError} Retry the lookup or start again with the reference.
          </p>
        ) : null}
        {lookupResult && !lookupLoading ? (
          <div className="mt-4">
            {lookupResult.items.length === 0 ? (
              <p>
                No matching assessments. Check the reference; an invitation
                without an assessment has no result.
              </p>
            ) : (
              <ul
                aria-label="Matching assessments"
                className="record-list divide-y divide-slate-200 border-y border-slate-200"
              >
                {lookupResult.items.map((item) => (
                  <li
                    key={item.assessment_id}
                    className="record-row min-w-0 py-4 [overflow-wrap:anywhere]"
                  >
                    <p className="break-all font-mono text-sm">
                      {item.assessment_id}
                    </p>
                    <p className="mt-2 text-sm">Created: {item.created_at}</p>
                    <p className="text-sm">
                      Submitted: {item.submitted_at ?? "Not submitted"}
                    </p>
                    <p className="text-sm">
                      Retention deadline:{" "}
                      {item.retention_expires_at ?? "Not set"}
                    </p>
                    <p className="text-sm">
                      Anonymized:{" "}
                      {anonymizationConfirmations.get(item.assessment_id) ??
                        item.anonymized_at ??
                        "No"}
                    </p>
                    <button
                      type="button"
                      className="action-secondary mt-3 min-h-11 max-w-full rounded-md border border-slate-300 px-4 py-2 text-sm font-semibold text-teal-700 focus-visible:outline-2 focus-visible:outline-teal-700"
                      disabled={working}
                      aria-pressed={assessmentId === item.assessment_id}
                      onClick={() => selectAssessment(item.assessment_id)}
                    >
                      Select assessment {item.assessment_id}
                    </button>
                  </li>
                ))}
              </ul>
            )}
            {lookupResult.next_cursor ? (
              <button
                type="button"
                className="action-secondary mt-4 min-h-11 rounded-md border border-slate-300 px-4 text-sm font-semibold focus-visible:outline-2 focus-visible:outline-teal-700"
                disabled={working}
                onClick={() => void handleLookup(true)}
              >
                Next assessment page
              </button>
            ) : null}
          </div>
        ) : null}
      </section>

      <section
        aria-labelledby="rights-title"
        className="surface mt-6 border-b border-slate-200 bg-white p-4 [overflow-wrap:anywhere]"
      >
        <h2 className="text-lg font-semibold text-slate-950" id="rights-title">
          Complete a data-rights request
        </h2>
        <label className="field-label mt-4 block max-w-2xl text-sm font-medium text-slate-800">
          Assessment ID
          <input
            className="field-control mt-2 min-h-11 font-mono"
            onChange={(event) => {
              selectAssessment(event.target.value);
            }}
            disabled={working || lookupLoading}
            placeholder="00000000-0000-4000-8000-000000000000"
            value={assessmentId}
          />
        </label>
        <div className="mt-4 flex flex-wrap gap-3">
          <button
            className="action-secondary min-h-11 rounded-md border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-teal-700"
            disabled={!validAssessmentId || working || lookupLoading}
            onClick={() => void handleExport()}
            type="button"
          >
            Create JSON export
          </button>
          <button
            className="min-h-11 rounded-md border border-rose-700 px-4 py-2 text-sm font-semibold text-rose-800 disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-teal-700"
            disabled={!validAssessmentId || working || lookupLoading}
            onClick={() => setConfirmingDeletion(true)}
            type="button"
          >
            Prepare anonymization
          </button>
          <button
            className="action-secondary min-h-11 rounded-md border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-teal-700"
            disabled={!validAssessmentId || working || lookupLoading}
            onClick={() => void load(assessmentId.trim())}
            type="button"
          >
            Look up audit history
          </button>
        </div>
        {confirmingDeletion ? (
          <div className="mt-5 border-l-4 border-rose-700 bg-rose-50 p-4">
            <p className="text-sm leading-6 text-rose-950">
              Assessment {assessmentId.trim()}: this revokes candidate access,
              erases assessment payloads, and deletes derived reports. Immutable
              audit tombstones remain.
            </p>
            <button
              className="mt-3 min-h-11 rounded-md bg-rose-800 px-4 py-2 text-sm font-semibold text-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-700"
              disabled={working}
              onClick={() => void handleDeletion()}
              type="button"
            >
              Confirm anonymization
            </button>
            <button
              type="button"
              disabled={working}
              className="ml-3 min-h-11 px-4 text-sm font-semibold focus-visible:outline-2 focus-visible:outline-teal-700"
              onClick={() => setConfirmingDeletion(false)}
            >
              Cancel anonymization
            </button>
          </div>
        ) : null}
        {actionError ? (
          <p className="mt-4 text-sm font-semibold text-rose-800" role="alert">
            {actionError}
          </p>
        ) : null}
        {deletion ? (
          <p className="mt-4 border-l-4 border-emerald-700 bg-emerald-50 p-4 text-sm text-emerald-950">
            Assessment {deletion.assessment_id} was anonymized. Derived reports
            removed: {deletion.reports_deleted}.
          </p>
        ) : null}
        {exported && exportDownload ? (
          <div className="mt-5 border-l-4 border-teal-700 bg-teal-50 p-4">
            <p className="text-sm font-bold text-teal-950">
              Export ready for {exported.invitation.email}
            </p>
            <a
              className="mt-3 inline-flex min-h-11 items-center font-semibold text-teal-700 underline focus-visible:outline-2 focus-visible:outline-teal-700"
              download={`candidate-data-${exported.assessment.id}.json`}
              href={exportDownload}
            >
              Download JSON export
            </a>
          </div>
        ) : null}
      </section>

      <section aria-labelledby="audit-title" className="mt-6">
        <h2 className="text-lg font-semibold text-slate-950" id="audit-title">
          Immutable audit history
        </h2>
        <p className="mt-2 break-all text-sm text-slate-600">
          {state.auditAssessmentId
            ? `Related history for assessment ${state.auditAssessmentId}, including linked invitation, consent, and report events.`
            : "Organization-wide audit history, newest events first."}
        </p>
        {state.auditAssessmentId ? (
          <p className="mt-2 text-sm text-slate-600">
            Related history includes currently linked records. Events for
            deleted reports remain in organization-wide history but are not
            included here.
          </p>
        ) : null}
        {state.auditEvents.length === 0 ? (
          <p className="mt-4 border-y border-slate-200 bg-white p-4 text-sm text-slate-600">
            No matching audit events.
          </p>
        ) : (
          <ul
            aria-label="Audit events"
            className="record-list surface mt-4 divide-y divide-slate-200 border-y border-slate-200 bg-white"
          >
            {state.auditEvents.map((event) => (
              <li className="record-row min-w-0 p-4" key={event.id}>
                <p className="font-semibold text-slate-900 [overflow-wrap:anywhere]">
                  {event.event_type}
                </p>
                <p className="mt-1 break-all font-mono text-xs text-slate-500">
                  {event.entity_type} · {event.entity_id}
                </p>
                <p className="mt-1 text-xs text-slate-500">
                  {new Date(event.occurred_at).toLocaleString("en-CA")}
                </p>
                <p className="mt-2 break-all text-xs text-slate-600">
                  Actor: {event.actor_id ?? "system"}
                </p>
                <pre className="mt-2 max-w-full overflow-x-auto whitespace-pre-wrap bg-slate-50 p-3 text-xs text-slate-700 [overflow-wrap:anywhere]">
                  {JSON.stringify(event.details, null, 2)}
                </pre>
              </li>
            ))}
          </ul>
        )}
        {state.auditHasMore ? (
          <button
            className="action-secondary mt-4 min-h-11 rounded-md border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-teal-700"
            disabled={auditLoadingMore || working || lookupLoading}
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
