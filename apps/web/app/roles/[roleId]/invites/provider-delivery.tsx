"use client";

import { useRef, useState } from "react";
import {
  ApiClientError,
  getInvitationDelivery,
  reissueInvitation,
} from "../../../../lib/api-client";
import type {
  Invitation,
  ProviderInvitationDelivery,
} from "../../../../lib/invitation-contracts";
import { formatDate } from "../../../../lib/role-ui";

const button =
  "action-secondary min-h-11 rounded-md border border-slate-300 px-4 py-2 text-sm font-semibold disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-teal-700";
const guidance: Record<ProviderInvitationDelivery["status"], string> = {
  queued: "Queued for a provider attempt. Receipt is not confirmed.",
  retrying:
    "The outcome is uncertain. The worker will retry the original message within its retry window; do not create a replacement.",
  sent: "The provider accepted the message. Inbox delivery is not confirmed.",
  delivered:
    "The provider reports delivery to the recipient server. This does not establish reading or consent.",
  failed:
    "Delivery failed. Correct provider or recipient policy issues before explicitly replacing this invitation.",
  bounced:
    "The message bounced. Investigate the address before issuing a new invitation; reissue would preserve this address.",
  complained:
    "A complaint was reported. Investigate the complaint; do not resend automatically.",
  reissue_required:
    "The safe retry window ended or delivery cannot continue. Review the cause before explicitly replacing this invitation.",
  cancelled: "Provider delivery was cancelled. No provider retry is pending.",
};

export function ProviderDelivery({
  roleId,
  invitation,
  disabled,
  archived,
  onReissued,
  onBusyChange,
}: {
  roleId: string;
  invitation: Invitation;
  disabled: boolean;
  archived: boolean;
  onReissued: (replacement: Invitation) => void;
  onBusyChange: (busy: boolean) => void;
}) {
  const [delivery, setDelivery] = useState<ProviderInvitationDelivery | null>(
    null,
  );
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const requestId = useRef<string | null>(null);
  const lock = useRef(false);
  async function check() {
    if (lock.current) return;
    lock.current = true;
    setBusy(true);
    setMessage("");
    try {
      const result = await getInvitationDelivery(roleId, invitation.id);
      if (result.invite_id !== invitation.id)
        throw new Error("Mismatched delivery");
      setDelivery(result);
    } catch (error) {
      setDelivery(null);
      setMessage(
        error instanceof ApiClientError && error.status === 404
          ? "No provider delivery record is available. Local delivery and invitation history remain available."
          : "Provider delivery could not be checked. Check again before deciding whether to replace this invitation.",
      );
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }
  async function reissue() {
    if (lock.current) return;
    if (
      !requestId.current &&
      !window.confirm(
        `Replace the invitation for ${invitation.email}? This invalidates the old link and queues a new message to the same address. Continue only after reviewing the delivery issue.`,
      )
    )
      return;
    requestId.current ??= crypto.randomUUID();
    lock.current = true;
    setBusy(true);
    onBusyChange(true);
    setMessage("");
    let unresolved = false;
    try {
      const replacement = await reissueInvitation(roleId, invitation.id, {
        request_id: requestId.current,
      });
      setUncertain(false);
      setDelivery(null);
      requestId.current = null;
      onReissued(replacement);
    } catch (error) {
      const unknown =
        uncertain ||
        !(error instanceof ApiClientError) ||
        error.status === 0 ||
        error.status >= 500 ||
        error.code === "invalid_api_response";
      unresolved = unknown;
      setUncertain(unknown);
      setMessage(
        unknown
          ? "Replacement outcome is unknown. Do not start a new issuance or reload this page. Retry the same reissue request to reconcile its outcome."
          : "Replacement was not confirmed. Refresh invitation history and review eligibility, profile approval, and permissions before proceeding.",
      );
    } finally {
      lock.current = false;
      setBusy(false);
      onBusyChange(unresolved);
    }
  }
  const eligible =
    !archived &&
    invitation.status !== "consented" &&
    invitation.status !== "declined" &&
    (delivery?.status === "failed" || delivery?.status === "reissue_required");
  return (
    <section
      aria-label={`Provider delivery for ${invitation.email}`}
      className="space-y-2 text-sm"
    >
      <button
        className={button}
        disabled={disabled || busy || uncertain}
        onClick={() => void check()}
      >
        Check provider delivery
      </button>
      {delivery ? (
        <div>
          <p>
            Provider delivery:{" "}
            <strong>{delivery.status.replaceAll("_", " ")}</strong>
          </p>
          <p>{guidance[delivery.status]}</p>
          <p>
            Attempts: {delivery.attempt_count} · Retry cutoff:{" "}
            {formatDate(delivery.retry_until)} (UTC)
          </p>
          {delivery.status === "queued" || delivery.status === "retrying" ? (
            <p>Next attempt: {formatDate(delivery.next_attempt_at)} (UTC)</p>
          ) : null}
          {delivery.last_error_code === "delivery_delayed" ? (
            <p>Delivery is delayed; the provider owns downstream retries.</p>
          ) : null}
        </div>
      ) : null}
      {message ? <p role="status">{message}</p> : null}
      {eligible || uncertain ? (
        <button
          className={button}
          disabled={(disabled && !uncertain) || busy}
          aria-label={
            uncertain
              ? "Retry same reissue request"
              : `Reissue invitation for ${invitation.email}`
          }
          onClick={() => void reissue()}
        >
          {uncertain ? "Retry same reissue request" : "Reissue invitation"}
        </button>
      ) : null}
    </section>
  );
}
