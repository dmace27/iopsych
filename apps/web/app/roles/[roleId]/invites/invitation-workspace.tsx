"use client";

import Link from "next/link";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import {
  ApiClientError,
  getCurrentUser,
  getRole,
} from "../../../../lib/api-client";
import {
  getInvitations,
  revokeInvitation,
} from "../../../../lib/invitation-client";
import {
  canManageInvitations,
  type Invitation,
} from "../../../../lib/invitation-contracts";
import { formatDate } from "../../../../lib/role-ui";
import { EmptyState, LoadingState } from "../../../ui/workspace-states";

import { InvitationIssueForm } from "./invitation-issue-form";

const labels: Record<Invitation["status"], string> = {
  pending_delivery: "Pending delivery",
  active: "Active",
  consented: "Consented",
  declined: "Declined",
  revoked: "Revoked",
  expired: "Expired",
};
const deliveryLabels: Record<
  NonNullable<Invitation["delivery_state"]>,
  string
> = {
  queued: "Queued",
  sending: "Sending",
  sent: "Sent",
  uncertain: "Delivery uncertain",
  cancelled: "Delivery cancelled",
  expired: "Delivery expired",
};
function deliveryGuidance(item: Invitation): string {
  switch (item.delivery_state) {
    case "queued":
      return "Waiting for a delivery attempt. Receipt is not confirmed.";
    case "sending":
      return "A delivery attempt is in progress. Receipt is not confirmed.";
    case "sent":
      return "The delivery service recorded a successful send. Recipient receipt is not confirmed.";
    case "uncertain":
      return "The delivery attempt ended without a confirmed outcome. The message may have been sent; no automatic retry is pending.";
    case "cancelled":
      return "Delivery was cancelled. No delivery work is pending.";
    case "expired":
      return "The delivery window expired. No delivery work is pending.";
    default:
      return "No delivery queue state is available. Legacy invitations may have used synchronous delivery; the stored invitation status and sent time do not confirm receipt.";
  }
}
type Failure = { message: string; status: number; restart: boolean };
function failure(error: unknown): Failure {
  const status = error instanceof ApiClientError ? error.status : 0;
  const restart =
    error instanceof ApiClientError &&
    error.code === "invalid_invitation_cursor";
  return {
    status,
    restart,
    message: restart
      ? "This page reference is no longer valid. Restart the list."
      : status === 401
        ? "Your session has expired. Sign in again."
        : status === 403
          ? "Only recruiters and administrators can manage invitations."
          : status === 404
            ? "This role or invitation is unavailable."
            : status === 429
              ? "Too many requests. Wait before trying again."
              : "The invitation request could not be completed. Try again.",
  };
}
const button =
  "action-secondary min-h-11 rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-700";
export function InvitationWorkspace({ roleId }: { roleId: string }) {
  return <Invitations key={roleId} roleId={roleId} />;
}
function Invitations({ roleId }: { roleId: string }) {
  const [title, setTitle] = useState("");
  const [archived, setArchived] = useState(false);
  const [items, setItems] = useState<Invitation[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [ready, setReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [issuing, setIssuing] = useState(false);
  const [error, setError] = useState<Failure | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [announcement, setAnnouncement] = useState("");
  const cards = useRef(new Map<string, HTMLLIElement>());
  const status = useRef<HTMLDivElement>(null);
  const focusAfterUpdate = useRef<{
    id: string | null;
    origin: Element | null;
  } | null>(null);
  useLayoutEffect(() => {
    const destination = focusAfterUpdate.current;
    focusAfterUpdate.current = null;
    if (
      destination &&
      destination.origin instanceof HTMLButtonElement &&
      (document.activeElement === destination.origin ||
        document.activeElement === document.body)
    ) {
      (cards.current.get(destination.id ?? "") ?? status.current)?.focus();
    }
  }, [items, cursor]);
  const lock = useRef(false);
  const generation = useRef(0);
  const retry = useRef<() => void>(() => {});
  useEffect(() => {
    const version = ++generation.current;
    const ref = generation;
    void (async () => {
      const user = await getCurrentUser();
      if (!canManageInvitations(user.role))
        throw new ApiClientError("", { status: 403, code: "forbidden" });
      const [role, list] = await Promise.all([
        getRole(roleId),
        getInvitations(roleId),
      ]);
      if (ref.current !== version) return;
      setTitle(role.title);
      setArchived(role.status === "archived");
      setItems(list.items);
      setCursor(list.next_cursor);
      setReady(true);
    })().catch((error: unknown) => {
      if (ref.current === version) setError(failure(error));
    });
    return () => {
      ref.current++;
    };
  }, [roleId, attempt]);
  function restart() {
    setReady(false);
    setItems([]);
    setCursor(null);
    setError(null);
    setAnnouncement("");
    setAttempt((value) => value + 1);
  }
  async function act(invitation?: Invitation) {
    if (lock.current) return;
    if (
      invitation &&
      !window.confirm(
        `Revoke the invitation for ${invitation.email}? This invalidates their assessment link. It does not delete existing responses or reports.`,
      )
    )
      return;
    const origin = document.activeElement;
    lock.current = true;
    setBusy(true);
    setError(null);
    const version = generation.current;
    retry.current = () => {
      void act(invitation);
    };
    try {
      if (invitation) {
        const updated = await revokeInvitation(roleId, invitation.id);
        if (version !== generation.current) return;
        if (updated.status === "revoked") {
          focusAfterUpdate.current = { id: updated.id, origin };
        }
        setItems((rows) =>
          rows.map((row) => (row.id === updated.id ? updated : row)),
        );
        setAnnouncement("Invitation status refreshed after revocation.");
      } else if (cursor) {
        const list = await getInvitations(roleId, cursor);
        if (version !== generation.current) return;
        if (list.next_cursor === null) {
          focusAfterUpdate.current = {
            id:
              list.items.find(
                (item) => !items.some((row) => row.id === item.id),
              )?.id ?? null,
            origin,
          };
        }
        setItems((rows) => [
          ...rows,
          ...list.items.filter(
            (item) => !rows.some((row) => row.id === item.id),
          ),
        ]);
        setCursor(list.next_cursor);
        setAnnouncement(`${list.items.length} more invitations loaded.`);
      }
    } catch (error) {
      if (version === generation.current) setError(failure(error));
    } finally {
      if (version === generation.current) {
        lock.current = false;
        setBusy(false);
      }
    }
  }
  const denied =
    error?.status === 401 || error?.status === 403 || error?.status === 404;
  return (
    <main
      id="main-content"
      className="workspace-shell mx-auto max-w-6xl space-y-5 px-5 py-8 text-slate-900 sm:px-8"
    >
      <Link
        className="inline-flex min-h-11 items-center text-sm font-medium text-teal-700 underline focus-visible:outline-2 focus-visible:outline-teal-700"
        href={`/roles/${roleId}`}
      >
        ← Back to role profile
      </Link>
      <h1 className="workspace-title text-2xl font-semibold [overflow-wrap:anywhere]">
        {title ? `${title}: invitations` : "Invitations"}
      </h1>
      <p className="max-w-3xl text-sm leading-6 text-slate-600">
        Invitation history across all role profile versions, newest first.
        Invitation state and delivery state are shown separately. Recipient
        receipt and assessment submission are not reported here. Expiry dates do
        not change the displayed invitation state.
      </p>
      <div
        ref={status}
        role="status"
        aria-live="polite"
        tabIndex={-1}
        className="rounded-lg focus:ring-2 focus:ring-teal-700"
      >
        {announcement}
      </div>
      {!ready && !error ? <LoadingState label="Loading invitations" /> : null}
      {error ? (
        <div
          role="alert"
          className="space-y-3 rounded-lg border border-red-200 p-4"
        >
          <p>{error.message}</p>
          {error.status === 401 ? (
            <Link
              className="inline-flex min-h-11 items-center text-teal-700 underline focus-visible:outline-2 focus-visible:outline-teal-700"
              href={`/sign-in?returnTo=${encodeURIComponent(`/roles/${roleId}/invites`)}`}
            >
              Sign in to manage invitations
            </Link>
          ) : null}
          {!denied ? (
            <button
              className={button}
              disabled={busy || issuing}
              onClick={() =>
                error.restart || !ready ? restart() : retry.current()
              }
            >
              {error.restart ? "Restart list" : "Try again"}
            </button>
          ) : null}
        </div>
      ) : null}
      {title && !denied ? (
        archived ? (
          <p>Archived roles cannot issue invitations.</p>
        ) : (
          <InvitationIssueForm
            roleId={roleId}
            disabled={busy || !ready}
            onBusyChange={setIssuing}
            onIssued={() => {
              const refresh = () => {
                setError(null);
                setAttempt((value) => value + 1);
              };
              retry.current = refresh;
              refresh();
            }}
          />
        )
      ) : null}
      {ready && !denied ? (
        <>
          <button
            className={button}
            disabled={busy || issuing || !ready}
            onClick={restart}
          >
            Refresh invitation history
          </button>
          {items.length === 0 ? (
            <EmptyState
              title="No invitations yet"
              description="There are no recorded invitations for this role."
            />
          ) : (
            <ul
              aria-label="Invitation history"
              className="record-list surface divide-y divide-slate-200 border-y border-slate-200 bg-white"
            >
              {items.map((item) => (
                <li
                  key={item.id}
                  ref={(node) => {
                    if (node) cards.current.set(item.id, node);
                    else cards.current.delete(item.id);
                  }}
                  tabIndex={-1}
                  aria-label={`${item.email}: ${labels[item.status]}`}
                  className="record-row space-y-2 px-4 py-4 focus:ring-2 focus:ring-teal-700"
                >
                  <h2 className="break-all text-base font-semibold">
                    {item.email}
                  </h2>
                  <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm">
                    <p>
                      Stored invitation state:{" "}
                      <strong>{labels[item.status]}</strong>
                    </p>
                    <p>
                      Delivery state:{" "}
                      <strong>
                        {item.delivery_state
                          ? deliveryLabels[item.delivery_state]
                          : "Unknown"}
                      </strong>
                    </p>
                  </div>
                  <p className="text-sm">{deliveryGuidance(item)}</p>
                  {item.delivery_state === "uncertain" ||
                  item.delivery_state === "expired" ||
                  item.delivery_state === "cancelled" ? (
                    <p className="text-sm">
                      {item.status !== "revoked"
                        ? "To replace this invitation, explicitly revoke it first. "
                        : "This invitation is revoked. "}
                      {archived
                        ? "Archived roles cannot issue a replacement."
                        : "Then review and confirm a new invitation using the issuance form."}
                    </p>
                  ) : null}
                  <p className="break-all text-sm text-slate-600">
                    Profile ID: {item.role_profile_id}
                  </p>
                  <p className="text-sm text-slate-600">
                    Created {formatDate(item.created_at)} (UTC) · Expires{" "}
                    {formatDate(item.expires_at)} (UTC)
                  </p>
                  <p className="text-sm text-slate-600">
                    {item.sent_at
                      ? `Sent ${formatDate(item.sent_at)} (UTC)`
                      : "No sent time recorded"}{" "}
                    ·{" "}
                    {item.revoked_at
                      ? `Revoked ${formatDate(item.revoked_at)} (UTC)`
                      : "No revocation time recorded"}
                  </p>
                  {item.status !== "revoked" ? (
                    <button
                      className={button}
                      disabled={busy || issuing}
                      aria-label={`Revoke invitation for ${item.email}`}
                      onClick={() => void act(item)}
                    >
                      Revoke invitation
                    </button>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
          {cursor && !error?.restart ? (
            <button
              className={button}
              disabled={busy || issuing}
              onClick={() => void act()}
            >
              Load more invitations
            </button>
          ) : null}
          {busy ? <LoadingState label="Updating invitations" /> : null}
        </>
      ) : null}
    </main>
  );
}
