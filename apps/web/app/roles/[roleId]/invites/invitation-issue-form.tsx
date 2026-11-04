"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { ApiClientError, getRoleProfiles } from "../../../../lib/api-client";
import type { RoleProfile } from "../../../../lib/contracts";
import { issueInvitation } from "../../../../lib/invitation-issuance-client";
import { InvitationCreateSchema } from "../../../../lib/invitation-issuance-contracts";

const button =
  "min-h-11 rounded-lg border border-teal-700 px-4 py-2 font-bold text-teal-900 disabled:opacity-50 focus-visible:ring-2 focus-visible:ring-teal-700";
const field = "block min-h-11 w-full rounded-lg border border-slate-400 p-2";
export function InvitationIssueForm({
  roleId,
  onIssued,
  disabled = false,
  onBusyChange,
}: {
  roleId: string;
  onIssued: () => void;
  disabled?: boolean;
  onBusyChange?: (busy: boolean) => void;
}) {
  const [profiles, setProfiles] = useState<RoleProfile[] | null>(null);
  const [profileId, setProfileId] = useState("");
  const [email, setEmail] = useState("");
  const [expiry, setExpiry] = useState("");
  const [preview, setPreview] = useState(false);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [denied, setDenied] = useState(false);
  const [unauthorized, setUnauthorized] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const lock = useRef(false);
  const requestKey = useRef<string | null>(null);
  const alive = useRef(false);
  useEffect(() => {
    alive.current = true;
    let current = true;
    getRoleProfiles(roleId)
      .then((rows) => {
        if (current)
          setProfiles(rows.filter((row) => row.status === "approved"));
      })
      .catch((reason: unknown) => {
        if (current) showError(reason);
      });
    return () => {
      current = false;
      alive.current = false;
    };
  }, [roleId, attempt]);
  function showError(reason: unknown) {
    const status = reason instanceof ApiClientError ? reason.status : 0;
    setDenied([401, 403, 404].includes(status));
    setUnauthorized(status === 401);
    setError(
      status === 401
        ? "Your session has expired. Sign in again."
        : status === 403 || status === 404
          ? "Invitation issuance is unavailable for this role or account."
          : status === 409 || status === 422
            ? "The server rejected this request. Check the approved profile, role availability, and expiry policy."
            : status === 429
              ? "Too many requests. Wait before retrying."
              : "The invitation outcome may be unknown. Check invitation history before retrying. Retrying keeps the same request key; delivery is not guaranteed.",
    );
  }
  function edit() {
    requestKey.current = null;
    setPreview(false);
    setDone(false);
    setError("");
    setMessage("");
  }
  const selected = profiles?.find((profile) => profile.id === profileId);
  const parsed = InvitationCreateSchema.safeParse({
    role_profile_id: profileId,
    email,
    ...(expiry === "" ? {} : { expires_in_hours: Number(expiry) }),
  });
  async function confirm() {
    if (
      disabled ||
      lock.current ||
      done ||
      denied ||
      !preview ||
      !parsed.success ||
      !selected
    )
      return;
    lock.current = true;
    setBusy(true);
    onBusyChange?.(true);
    setError("");
    try {
      requestKey.current ??= crypto.randomUUID();
      const result = await issueInvitation(
        roleId,
        parsed.data,
        requestKey.current,
      );
      if (!alive.current) return;
      setDone(true);
      setMessage(
        `Invitation recorded. Stored status: ${result.status === "pending_delivery" ? "Pending delivery" : result.status}. Delivery receipt is not confirmed here.`,
      );
      onIssued();
    } catch (reason) {
      if (alive.current) showError(reason);
    } finally {
      lock.current = false;
      if (alive.current) {
        setBusy(false);
        onBusyChange?.(false);
      }
    }
  }
  return (
    <section
      aria-labelledby="issue-heading"
      className="space-y-4 rounded-xl border border-slate-200 p-5"
    >
      <h2 id="issue-heading" className="text-xl font-bold">
        Issue invitation
      </h2>
      <p>
        The server checks role availability, profile approval, expiry policy,
        and assessment eligibility when issuing.
      </p>
      {error ? <div role="alert">{error}</div> : null}
      {unauthorized ? (
        <Link
          href={`/sign-in?returnTo=${encodeURIComponent(`/roles/${roleId}/invites`)}`}
        >
          Sign in to issue invitations
        </Link>
      ) : null}
      {!profiles && !error ? (
        <p role="status">Loading approved profile versions</p>
      ) : null}
      {!profiles && error && !denied ? (
        <button
          className={button}
          onClick={() => {
            setError("");
            setAttempt((value) => value + 1);
          }}
        >
          Retry profile loading
        </button>
      ) : null}
      {profiles?.length === 0 ? (
        <p>No approved profile versions are available.</p>
      ) : null}
      {profiles && profiles.length > 0 && !denied ? (
        <form
          className="space-y-4"
          onSubmit={(event) => {
            event.preventDefault();
            if (parsed.success && selected) {
              setError("");
              setPreview(true);
            }
          }}
        >
          <fieldset disabled={disabled || busy || done} className="space-y-4">
            <label className="block">
              Recipient email
              <input
                className={field}
                type="email"
                required
                maxLength={320}
                value={email}
                onChange={(event) => {
                  edit();
                  setEmail(event.target.value);
                }}
              />
            </label>
            <label className="block">
              Approved profile version
              <select
                className={field}
                required
                value={profileId}
                onChange={(event) => {
                  edit();
                  setProfileId(event.target.value);
                }}
              >
                <option value="">Select a version</option>
                {profiles.map((profile) => (
                  <option key={profile.id} value={profile.id}>
                    Version {profile.version} — {profile.id}
                  </option>
                ))}
              </select>
            </label>
            <label className="block">
              Requested expiry in hours (optional)
              <input
                className={field}
                type="number"
                min={1}
                max={720}
                step={1}
                value={expiry}
                onChange={(event) => {
                  edit();
                  setExpiry(event.target.value);
                }}
              />
            </label>
            <p>Leave expiry blank to use the server default.</p>
            <button
              className={button}
              type="submit"
              disabled={!parsed.success || !selected}
            >
              Review invitation
            </button>
          </fieldset>
          {preview && parsed.success && selected ? (
            <div className="space-y-3" aria-label="Invitation preview">
              <h3 className="font-bold">Confirm invitation request</h3>
              <p>Recipient: {parsed.data.email}</p>
              <p>
                Profile version: {selected.version} ({selected.id})
              </p>
              <p>
                Requested expiry:{" "}
                {expiry === ""
                  ? "Server default"
                  : `${expiry} hours from issuance`}
              </p>
              <button
                type="button"
                className={button}
                disabled={disabled || busy || done}
                onClick={() => void confirm()}
              >
                {busy
                  ? "Issuing invitation…"
                  : error
                    ? "Confirm and retry invitation"
                    : "Confirm and issue invitation"}
              </button>
            </div>
          ) : null}
        </form>
      ) : null}
      <p role="status" aria-live="polite">
        {message}
      </p>
      {done ? (
        <button
          className={button}
          onClick={() => {
            edit();
            setEmail("");
          }}
        >
          Start new invitation
        </button>
      ) : null}
    </section>
  );
}
