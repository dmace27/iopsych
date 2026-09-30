"use client";

import {
  AssessmentResponseSetSchema,
  PILOT_ASSESSMENT_DEFINITION_V1,
  type AssessmentBlock,
  type AssessmentBlockResponse,
  type AssessmentItem,
  type AssessmentResponseSet,
} from "@iopsych/shared";
import { useEffect, useMemo, useRef, useState } from "react";

import {
  getCandidateInvite,
  recordCandidateConsent,
  submitCandidateAssessment,
} from "../../../../lib/candidate-api";
import type {
  CandidateCompletion,
  CandidateInvite,
  ConsentDecision,
} from "../../../../lib/candidate-contracts";
import {
  completeCandidateAssessment,
  loadCandidateCompletion,
  loadCandidateDraft,
  saveCandidateDraft,
} from "../../../../lib/candidate-storage";

interface CandidateAssessmentProps {
  token: string;
}

interface BlockChoice {
  leastLikeItemId?: string;
  mostLikeItemId?: string;
  skipped: boolean;
}

type Choices = Record<string, BlockChoice>;
type View = "consent" | "assessment" | "review" | "declined" | "complete";
type LoadState =
  | { status: "loading" }
  | { message: string; status: "error" }
  | {
      completion: CandidateCompletion | null;
      invite: CandidateInvite;
      status: "ready";
      view: View;
    };

const assessment = PILOT_ASSESSMENT_DEFINITION_V1;

/** Produce a stable per-invitation statement order without extra stored state. */
function orderedItems(
  block: AssessmentBlock,
  invitationId: string,
): AssessmentItem[] {
  function stableWeight(value: string): number {
    let hash = 2166136261;
    for (const character of value) {
      hash ^= character.charCodeAt(0);
      hash = Math.imul(hash, 16777619);
    }
    return hash >>> 0;
  }
  return [...block.items].sort(
    (left, right) =>
      stableWeight(invitationId + ":" + left.id) -
      stableWeight(invitationId + ":" + right.id),
  );
}

function choicesFromResponses(responses: AssessmentBlockResponse[]): Choices {
  return Object.fromEntries(
    responses.map((response) => [
      response.block_id,
      response.skipped
        ? { skipped: true }
        : {
            leastLikeItemId: response.least_like_item_id,
            mostLikeItemId: response.most_like_item_id,
            skipped: false,
          },
    ]),
  );
}

/** Include only complete choices so persisted snapshots stay contract-valid. */
function responseSetFromChoices(choices: Choices): AssessmentResponseSet {
  const responses: AssessmentBlockResponse[] = [];
  for (const block of assessment.blocks) {
    const choice = choices[block.id];
    if (choice?.skipped) {
      responses.push({
        block_id: block.id,
        least_like_item_id: null,
        most_like_item_id: null,
        skipped: true,
      });
    } else if (choice?.mostLikeItemId && choice.leastLikeItemId) {
      responses.push({
        block_id: block.id,
        least_like_item_id: choice.leastLikeItemId,
        most_like_item_id: choice.mostLikeItemId,
        skipped: false,
      });
    }
  }
  return AssessmentResponseSetSchema.parse({
    assessment_definition_id: assessment.id,
    assessment_definition_version: assessment.version,
    responses,
  });
}

function inviteErrorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  return "This invitation could not be opened. Ask your contact for help.";
}

function formatExpiry(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return value;
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "long",
    timeStyle: "short",
  }).format(date);
}

/** Public, consent-gated candidate journey for one bearer invitation. */
export function CandidateAssessment({ token }: CandidateAssessmentProps) {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [choices, setChoices] = useState<Choices>({});
  const [currentBlockIndex, setCurrentBlockIndex] = useState(0);
  const [submittingConsent, setSubmittingConsent] = useState(false);
  const [submittingAssessment, setSubmittingAssessment] = useState(false);
  const submissionPending = useRef(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [resumedDraft, setResumedDraft] = useState(false);
  const headingRef = useRef<HTMLHeadingElement>(null);
  const firstMostRef = useRef<HTMLInputElement>(null);

  const responseSet = useMemo(() => responseSetFromChoices(choices), [choices]);

  useEffect(() => {
    let active = true;
    void getCandidateInvite(token)
      .then((invite) => {
        if (!active) return;
        if (invite.decision === "decline") {
          setState({
            completion: null,
            invite,
            status: "ready",
            view: "declined",
          });
          return;
        }
        if (invite.can_start_assessment) {
          if (invite.assessment_id) {
            setState({
              completion: null,
              invite,
              status: "ready",
              view: "complete",
            });
            return;
          }
          const completion = loadCandidateCompletion(
            window.localStorage,
            invite.invitation_id,
          );
          const draft =
            loadCandidateDraft(window.localStorage, invite.invitation_id) ??
            completion;
          if (
            draft?.response_set.assessment_definition_id === assessment.id &&
            draft.response_set.assessment_definition_version ===
              assessment.version
          ) {
            setChoices(choicesFromResponses(draft.response_set.responses));
            setResumedDraft(true);
            const completedBlockIds = new Set(
              draft.response_set.responses.map(({ block_id }) => block_id),
            );
            const firstIncomplete = assessment.blocks.findIndex(
              ({ id }) => !completedBlockIds.has(id),
            );
            setCurrentBlockIndex(
              firstIncomplete === -1
                ? assessment.blocks.length - 1
                : firstIncomplete,
            );
          }
          setState({
            completion,
            invite,
            status: "ready",
            view: completion ? "review" : "assessment",
          });
          return;
        }
        setState({
          completion: null,
          invite,
          status: "ready",
          view: "consent",
        });
      })
      .catch((error: unknown) => {
        if (active) {
          setState({ message: inviteErrorMessage(error), status: "error" });
        }
      });
    return () => {
      active = false;
    };
  }, [token]);

  const persistedInvitationId =
    state.status === "ready" &&
    state.invite.can_start_assessment &&
    state.view !== "complete"
      ? state.invite.invitation_id
      : null;

  useEffect(() => {
    if (persistedInvitationId === null || responseSet.responses.length === 0) {
      return;
    }
    try {
      saveCandidateDraft(
        window.localStorage,
        persistedInvitationId,
        responseSet,
      );
    } catch {
      // Device storage may be disabled; responses can still be submitted to the server.
    }
  }, [persistedInvitationId, responseSet]);

  const currentView = state.status === "ready" ? state.view : null;
  useEffect(() => {
    if (state.status === "ready") headingRef.current?.focus();
  }, [currentBlockIndex, currentView, state.status]);

  async function decide(decision: ConsentDecision) {
    setSubmittingConsent(true);
    setActionError(null);
    try {
      const invite = await recordCandidateConsent(token, decision);
      setState({
        completion: null,
        invite,
        status: "ready",
        view: decision === "consent" ? "assessment" : "declined",
      });
    } catch (error) {
      setActionError(inviteErrorMessage(error));
      setSubmittingConsent(false);
    }
  }

  function updateChoice(
    blockId: string,
    kind: "most" | "least" | "skip",
    itemId?: string,
  ) {
    setValidationError(null);
    setChoices((current) => {
      const existing = current[blockId] ?? { skipped: false };
      if (kind === "skip") {
        return {
          ...current,
          [blockId]: { skipped: !existing.skipped },
        };
      }
      if (kind === "most") {
        return {
          ...current,
          [blockId]: {
            leastLikeItemId:
              existing.leastLikeItemId === itemId
                ? undefined
                : existing.leastLikeItemId,
            mostLikeItemId: itemId,
            skipped: false,
          },
        };
      }
      return {
        ...current,
        [blockId]: {
          leastLikeItemId: itemId,
          mostLikeItemId:
            existing.mostLikeItemId === itemId
              ? undefined
              : existing.mostLikeItemId,
          skipped: false,
        },
      };
    });
  }

  function goForward(block: AssessmentBlock) {
    const choice = choices[block.id];
    if (
      !choice?.skipped &&
      !(choice?.mostLikeItemId && choice.leastLikeItemId)
    ) {
      setValidationError(
        "Choose one statement in each column, or select “Prefer not to answer this block.”",
      );
      window.setTimeout(() => firstMostRef.current?.focus(), 0);
      return;
    }
    if (currentBlockIndex === assessment.blocks.length - 1) {
      setState((current) =>
        current.status === "ready" ? { ...current, view: "review" } : current,
      );
      return;
    }
    setCurrentBlockIndex((index) => index + 1);
  }

  async function submitAssessment() {
    if (state.status !== "ready" || submissionPending.current) return;
    if (responseSet.responses.length !== assessment.blocks.length) {
      setValidationError(
        "Review every block before submitting. Each block must be answered or skipped.",
      );
      return;
    }
    submissionPending.current = true;
    setSubmittingAssessment(true);
    setValidationError(null);
    try {
      const receipt = await submitCandidateAssessment(token, responseSet);
      let completion: CandidateCompletion | null = null;
      try {
        completion = completeCandidateAssessment(
          window.localStorage,
          state.invite.invitation_id,
          responseSet,
          receipt.assessment_id,
        );
      } catch {
        // Server persistence is authoritative even if device storage is unavailable.
      }
      setState({
        ...state,
        completion,
        invite: { ...state.invite, assessment_id: receipt.assessment_id },
        view: "complete",
      });
    } catch (error: unknown) {
      setValidationError(
        error instanceof Error
          ? error.message
          : "Submission failed. Try again.",
      );
    } finally {
      submissionPending.current = false;
      setSubmittingAssessment(false);
    }
  }

  if (state.status === "loading") {
    return (
      <main
        aria-busy="true"
        className="mx-auto max-w-4xl px-5 py-12 sm:px-8"
        id="main-content"
      >
        <p className="text-sm font-bold text-teal-800">Opening invitation…</p>
        <div className="skeleton-shimmer mt-5 h-56 rounded-3xl" />
      </main>
    );
  }

  if (state.status === "error") {
    return (
      <main className="mx-auto max-w-3xl px-5 py-16 sm:px-8" id="main-content">
        <section className="rounded-3xl border border-rose-200 bg-white p-7 shadow-sm sm:p-10">
          <p className="text-sm font-bold uppercase tracking-[0.16em] text-rose-800">
            Invitation unavailable
          </p>
          <h1 className="mt-3 text-3xl font-bold text-slate-950">
            We could not open this assessment
          </h1>
          <p className="mt-4 leading-7 text-slate-700" role="alert">
            {state.message}
          </p>
        </section>
      </main>
    );
  }

  const { invite, view } = state;
  const privacyHref =
    "mailto:" +
    invite.consent_notice.privacy_contact_email +
    "?subject=" +
    encodeURIComponent("Candidate data rights request") +
    (invite.assessment_id
      ? "&body=" +
        encodeURIComponent(
          `Assessment reference: ${invite.assessment_id}\n\nPlease describe whether you are requesting a copy, correction, or deletion.`,
        )
      : "");
  const accommodationHref =
    "mailto:" +
    invite.consent_notice.accommodation_contact_email +
    "?subject=" +
    encodeURIComponent("Assessment accommodation request");

  if (view === "declined") {
    return (
      <CandidateFrame invite={invite} privacyHref={privacyHref}>
        <section className="rounded-3xl border border-slate-200 bg-white p-7 shadow-sm sm:p-10">
          <p className="text-sm font-bold uppercase tracking-[0.16em] text-teal-800">
            Choice recorded
          </p>
          <h1
            className="mt-3 text-3xl font-bold text-slate-950"
            ref={headingRef}
            tabIndex={-1}
          >
            You declined the assessment
          </h1>
          <p className="mt-4 max-w-2xl leading-7 text-slate-700">
            Your decision has been recorded. Declining carries no penalty in
            this pilot, and no assessment questions or responses were collected.
          </p>
          <p className="mt-4 text-sm text-slate-600">
            You can close this window now.
          </p>
        </section>
      </CandidateFrame>
    );
  }

  if (view === "complete") {
    return (
      <CandidateFrame invite={invite} privacyHref={privacyHref}>
        <section className="rounded-3xl border border-teal-200 bg-white p-7 shadow-sm sm:p-10">
          <div
            aria-hidden="true"
            className="grid size-12 place-items-center rounded-full bg-teal-100 text-2xl text-teal-900"
          >
            ✓
          </div>
          <h1
            className="mt-5 text-3xl font-bold text-slate-950"
            ref={headingRef}
            tabIndex={-1}
          >
            Your responses are complete
          </h1>
          <p className="mt-4 max-w-2xl leading-7 text-slate-700">
            Thank you. Your work-preference responses were recorded for the
            human-reviewed pilot. This assessment does not make a hiring
            decision.
          </p>
          <div className="mt-7 rounded-2xl bg-slate-50 p-5">
            <h2 className="font-bold text-slate-950">What happens next?</h2>
            <p className="mt-2 text-sm leading-6 text-slate-700">
              A recruiter may use your responses to prepare neutral interview
              questions. We do not show or create a single overall fit score
              here.
            </p>
          </div>
          <p className="mt-6 text-sm leading-6 text-slate-600">
            Want a copy, correction, or deletion? Use the{" "}
            <a
              className="font-bold text-teal-800 underline underline-offset-4 hover:text-teal-950"
              href={privacyHref}
            >
              data-rights contact
            </a>
            .
          </p>
        </section>
      </CandidateFrame>
    );
  }

  if (view === "consent") {
    return (
      <CandidateFrame invite={invite} privacyHref={privacyHref}>
        <section
          aria-labelledby="consent-title"
          className="rounded-3xl border border-slate-200 bg-white p-7 shadow-sm sm:p-10"
        >
          <p className="text-sm font-bold uppercase tracking-[0.16em] text-teal-800">
            Before you begin
          </p>
          <h1
            className="mt-3 text-3xl font-bold tracking-tight text-slate-950 sm:text-4xl"
            id="consent-title"
            ref={headingRef}
            tabIndex={-1}
          >
            Your choice and your data
          </h1>
          <p className="mt-4 max-w-2xl text-base leading-7 text-slate-700">
            Review this information before deciding. Assessment questions remain
            hidden until you give affirmative consent.
          </p>
          <dl className="mt-8 grid gap-5 sm:grid-cols-2">
            <ConsentDetail
              description={invite.consent_notice.purpose}
              term="Purpose"
            />
            <ConsentDetail
              description={invite.consent_notice.data_use}
              term="How your data is used"
            />
            <ConsentDetail
              description={invite.consent_notice.retention}
              term="Retention"
            />
            <ConsentDetail
              description={
                <>
                  For an adjustment or another way to complete this assessment,
                  email{" "}
                  <a
                    className="font-bold text-teal-800 underline underline-offset-4"
                    href={accommodationHref}
                  >
                    {invite.consent_notice.accommodation_contact_email}
                  </a>
                  .
                </>
              }
              term="Accommodation"
            />
          </dl>
          <div className="mt-7 rounded-2xl border border-amber-200 bg-amber-50 p-5 text-sm leading-6 text-amber-950">
            <strong>Your participation is voluntary.</strong>{" "}
            {invite.consent_notice.decline_without_penalty
              ? "You may decline without penalty."
              : "Contact the privacy team if you have questions before choosing."}
          </div>
          {actionError ? (
            <p className="mt-5 font-semibold text-rose-800" role="alert">
              {actionError}
            </p>
          ) : null}
          <div className="mt-7 flex flex-col gap-3 sm:flex-row">
            <button
              className="min-h-12 rounded-xl bg-teal-800 px-6 py-3 font-bold text-white hover:bg-teal-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-700 focus-visible:ring-offset-2"
              disabled={submittingConsent}
              onClick={() => void decide("consent")}
              type="button"
            >
              {submittingConsent
                ? "Recording your choice…"
                : "I consent and want to begin"}
            </button>
            <button
              className="min-h-12 rounded-xl border border-slate-300 bg-white px-6 py-3 font-bold text-slate-800 hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-700 focus-visible:ring-offset-2"
              disabled={submittingConsent}
              onClick={() => void decide("decline")}
              type="button"
            >
              I decline
            </button>
          </div>
          <p className="mt-5 text-xs leading-5 text-slate-500">
            Consent notice version {invite.consent_notice.version}
          </p>
        </section>
      </CandidateFrame>
    );
  }

  if (view === "review") {
    return (
      <CandidateFrame invite={invite} privacyHref={privacyHref}>
        <section className="rounded-3xl border border-slate-200 bg-white p-7 shadow-sm sm:p-10">
          <p className="text-sm font-bold uppercase tracking-[0.16em] text-teal-800">
            Review
          </p>
          <h1
            className="mt-3 text-3xl font-bold text-slate-950"
            ref={headingRef}
            tabIndex={-1}
          >
            Review your responses
          </h1>
          <p className="mt-3 leading-7 text-slate-700">
            All six blocks are ready. You can return to any block before
            submitting.
          </p>
          <ol className="mt-7 divide-y divide-slate-200 rounded-2xl border border-slate-200">
            {assessment.blocks.map((block, index) => {
              const choice = choices[block.id];
              return (
                <li
                  className="flex items-center justify-between gap-4 p-4"
                  key={block.id}
                >
                  <span className="font-semibold text-slate-800">
                    Block {index + 1}:{" "}
                    <span className="font-normal text-slate-600">
                      {choice?.skipped ? "Prefer not to answer" : "Answered"}
                    </span>
                  </span>
                  <button
                    className="rounded-lg px-3 py-2 text-sm font-bold text-teal-800 underline underline-offset-4 hover:text-teal-950 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-700"
                    onClick={() => {
                      setCurrentBlockIndex(index);
                      setState({ ...state, view: "assessment" });
                    }}
                    disabled={submittingAssessment}
                    type="button"
                  >
                    Change block {index + 1}
                  </button>
                </li>
              );
            })}
          </ol>
          {validationError ? (
            <p className="mt-5 font-semibold text-rose-800" role="alert">
              {validationError}
            </p>
          ) : null}
          <div className="mt-7 flex flex-col gap-3 sm:flex-row">
            <button
              className="min-h-12 rounded-xl bg-teal-800 px-6 py-3 font-bold text-white hover:bg-teal-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-700 focus-visible:ring-offset-2"
              onClick={submitAssessment}
              disabled={submittingAssessment}
              type="button"
            >
              {submittingAssessment ? "Submitting…" : "Submit my responses"}
            </button>
            <button
              className="min-h-12 rounded-xl border border-slate-300 bg-white px-6 py-3 font-bold text-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-700"
              onClick={() => {
                setCurrentBlockIndex(assessment.blocks.length - 1);
                setState({ ...state, view: "assessment" });
              }}
              disabled={submittingAssessment}
              type="button"
            >
              Back to assessment
            </button>
          </div>
        </section>
      </CandidateFrame>
    );
  }

  const block = assessment.blocks[currentBlockIndex]!;
  const choice = choices[block.id] ?? { skipped: false };
  const items = orderedItems(block, invite.invitation_id);
  const progress = ((currentBlockIndex + 1) / assessment.blocks.length) * 100;

  return (
    <CandidateFrame invite={invite} privacyHref={privacyHref}>
      <div className="mb-6" role="status">
        <div className="flex items-center justify-between gap-4 text-sm font-semibold text-slate-700">
          <span>
            Block {currentBlockIndex + 1} of {assessment.blocks.length}
          </span>
          <span>
            {resumedDraft || responseSet.responses.length > 0
              ? "Saved on this device"
              : "Not saved yet"}
          </span>
        </div>
        <div
          aria-hidden="true"
          className="mt-2 h-2 overflow-hidden rounded-full bg-slate-200"
        >
          <div
            className="h-full rounded-full bg-teal-700"
            style={{ width: String(progress) + "%" }}
          />
        </div>
      </div>
      <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm sm:p-9">
        <h1
          className="text-3xl font-bold tracking-tight text-slate-950"
          ref={headingRef}
          tabIndex={-1}
        >
          Which statements are most and least like you?
        </h1>
        <p className="mt-3 max-w-3xl leading-7 text-slate-700">
          Choose one statement in each column. There are no right or wrong
          answers.
        </p>
        <fieldset className="mt-7">
          <legend className="sr-only">
            Work-preference statements for block {currentBlockIndex + 1}
          </legend>
          <div className="hidden grid-cols-[1fr_7rem_7rem] gap-3 border-b border-slate-300 px-4 pb-3 text-center text-xs font-bold uppercase tracking-wide text-slate-600 sm:grid">
            <span className="text-left">Statement</span>
            <span>Most like me</span>
            <span>Least like me</span>
          </div>
          <div className="divide-y divide-slate-200">
            {items.map((item, index) => (
              <div
                className="grid gap-4 px-2 py-5 sm:grid-cols-[1fr_7rem_7rem] sm:items-center sm:px-4"
                key={item.id}
              >
                <p className="font-medium leading-6 text-slate-900">
                  {item.statement}
                </p>
                <label className="flex min-h-11 items-center gap-3 rounded-lg px-2 text-sm font-semibold text-slate-700 sm:justify-center sm:px-0">
                  <input
                    aria-label={"Most like me: " + item.statement}
                    checked={choice.mostLikeItemId === item.id}
                    className="size-5 accent-teal-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-700"
                    disabled={choice.skipped}
                    name={"most-" + block.id}
                    onChange={() => updateChoice(block.id, "most", item.id)}
                    ref={index === 0 ? firstMostRef : undefined}
                    type="radio"
                    value={item.id}
                  />
                  <span aria-hidden="true" className="sm:hidden">
                    Most like me
                  </span>
                </label>
                <label className="flex min-h-11 items-center gap-3 rounded-lg px-2 text-sm font-semibold text-slate-700 sm:justify-center sm:px-0">
                  <input
                    aria-label={"Least like me: " + item.statement}
                    checked={choice.leastLikeItemId === item.id}
                    className="size-5 accent-teal-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-700"
                    disabled={choice.skipped}
                    name={"least-" + block.id}
                    onChange={() => updateChoice(block.id, "least", item.id)}
                    type="radio"
                    value={item.id}
                  />
                  <span aria-hidden="true" className="sm:hidden">
                    Least like me
                  </span>
                </label>
              </div>
            ))}
          </div>
          <label className="mt-4 flex min-h-12 items-center gap-3 rounded-xl border border-slate-300 bg-slate-50 px-4 py-3 font-semibold text-slate-800">
            <input
              checked={choice.skipped}
              className="size-5 accent-teal-700"
              onChange={() => updateChoice(block.id, "skip")}
              type="checkbox"
            />
            Prefer not to answer this block
          </label>
        </fieldset>
        {validationError ? (
          <p
            className="mt-5 rounded-xl border border-rose-200 bg-rose-50 p-4 font-semibold text-rose-900"
            role="alert"
          >
            {validationError}
          </p>
        ) : null}
        <div className="mt-7 flex flex-col-reverse gap-3 sm:flex-row sm:justify-between">
          <button
            className="min-h-12 rounded-xl border border-slate-300 bg-white px-6 py-3 font-bold text-slate-800 hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-700 disabled:opacity-50"
            disabled={currentBlockIndex === 0}
            onClick={() => {
              setValidationError(null);
              setCurrentBlockIndex((index) => Math.max(0, index - 1));
            }}
            type="button"
          >
            Previous block
          </button>
          <button
            className="min-h-12 rounded-xl bg-teal-800 px-6 py-3 font-bold text-white hover:bg-teal-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-700 focus-visible:ring-offset-2"
            onClick={() => goForward(block)}
            type="button"
          >
            {currentBlockIndex === assessment.blocks.length - 1
              ? "Review answers"
              : "Save and continue"}
          </button>
        </div>
      </section>
    </CandidateFrame>
  );
}

function CandidateFrame({
  children,
  invite,
  privacyHref,
}: {
  children: React.ReactNode;
  invite: CandidateInvite;
  privacyHref: string;
}) {
  return (
    <main
      className="mx-auto max-w-4xl px-5 py-10 sm:px-8 sm:py-14"
      id="main-content"
    >
      <div className="mb-7 border-b border-slate-300 pb-6">
        <p className="text-xs font-bold uppercase tracking-[0.18em] text-teal-800">
          {invite.organization_name}
        </p>
        <p className="mt-2 text-xl font-bold text-slate-950">
          {invite.role_title}
        </p>
        <p className="mt-1 text-sm text-slate-600">
          Invitation expires {formatExpiry(invite.expires_at)}
        </p>
      </div>
      {children}
      <footer className="mt-8 flex flex-col justify-between gap-3 border-t border-slate-300 pt-6 text-sm text-slate-600 sm:flex-row">
        <span>Work-preference pilot · Human reviewed</span>
        <a
          className="font-bold text-teal-800 underline underline-offset-4 hover:text-teal-950 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-700"
          href={privacyHref}
        >
          Request a copy, correction, or deletion
        </a>
      </footer>
    </main>
  );
}

function ConsentDetail({
  description,
  term,
}: {
  description: React.ReactNode;
  term: string;
}) {
  return (
    <div className="rounded-2xl bg-slate-50 p-5">
      <dt className="font-bold text-slate-950">{term}</dt>
      <dd className="mt-2 text-sm leading-6 text-slate-700">{description}</dd>
    </div>
  );
}
