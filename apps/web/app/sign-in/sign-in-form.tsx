"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { safeReturnTo } from "../../lib/safe-return-to";

/** Exchange a short-lived provider token for the server-managed session cookie. */
export function SignInForm({
  localLogin = false,
  returnTo,
}: {
  localLogin?: boolean;
  returnTo?: string;
}) {
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    const data = new FormData(event.currentTarget);
    const token = String(data.get("token") ?? "").trim();

    try {
      const response = await fetch(
        localLogin ? "/api/session/local" : "/api/session",
        {
          body: JSON.stringify(
            localLogin ? { identity: data.get("identity") } : { token },
          ),
          headers: { "Content-Type": "application/json" },
          method: "POST",
        },
      );
      if (!response.ok) {
        const payload: unknown = await response.json().catch(() => null);
        const detail =
          typeof payload === "object" &&
          payload !== null &&
          "detail" in payload &&
          typeof payload.detail === "string"
            ? payload.detail
            : "The session could not be established.";
        throw new Error(detail);
      }
      router.replace(safeReturnTo(returnTo));
      router.refresh();
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The session could not be established.",
      );
      setSubmitting(false);
    }
  }

  return (
    <form
      className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8"
      onSubmit={handleSubmit}
    >
      {localLogin ? (
        <label className="block text-sm font-bold text-slate-800">
          Synthetic local account
          <select
            className="field-control mt-2"
            name="identity"
            disabled={submitting}
          >
            <option value="alpha">
              Alpha Recruiter — synthetic tenant Alpha
            </option>
            <option value="beacon">
              Beacon Manager — synthetic tenant Beacon
            </option>
          </select>
        </label>
      ) : (
        <label className="block text-sm font-bold text-slate-800">
          Internal access token
          <span className="mt-1 block text-xs font-normal leading-5 text-slate-500">
            Tokens are validated by the API before a session is created.
          </span>
          <input
            autoComplete="off"
            className="field-control mt-2"
            disabled={submitting}
            name="token"
            required
            spellCheck={false}
            type="password"
          />
        </label>
      )}
      {error ? (
        <p
          className="mt-4 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm font-semibold text-rose-900"
          role="alert"
        >
          {error}
        </p>
      ) : null}
      <button
        className="mt-5 min-h-11 rounded-xl bg-teal-800 px-5 py-2.5 text-sm font-bold text-white hover:bg-teal-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-700 focus-visible:ring-offset-2"
        disabled={submitting}
        type="submit"
      >
        {submitting ? "Validating session…" : "Continue to roles"}
      </button>
    </form>
  );
}
