"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { safeReturnTo } from "../../lib/safe-return-to";

/** Exchange a short-lived provider token for the server-managed session cookie. */
export function SignInForm({
  localLogin = false,
  tokenLogin = false,
  providerError,
  returnTo,
}: {
  localLogin?: boolean;
  tokenLogin?: boolean;
  providerError?: string;
  returnTo?: string;
}) {
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!localLogin && !tokenLogin) {
    return (
      <div className="signin-form">
        {providerError ? (
          <p role="alert" className="mb-4 text-rose-900">
            {providerError === "configuration"
              ? "Sign-in is not configured. Contact your administrator."
              : "Sign-in could not be completed. Try again or ask your administrator to check your access."}
          </p>
        ) : null}
        <a
          className="action-primary flex min-h-12 w-full items-center justify-center gap-3 rounded-lg bg-[var(--text)] px-5 py-3 text-sm font-medium text-white focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[var(--accent)]"
          href={`/api/auth/login?${new URLSearchParams({ returnTo: safeReturnTo(returnTo) })}`}
        >
          Sign in with Auth0
        </a>
        <p className="mt-4 text-sm text-slate-600">
          Use the account provided by your administrator.
        </p>
      </div>
    );
  }

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
    <form className="signin-form" onSubmit={handleSubmit}>
      {localLogin ? (
        <label className="block text-sm font-medium text-[var(--text)]">
          Synthetic local account
          <select
            className="field-control mt-3 min-h-12 rounded-lg"
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
        <label className="block text-sm font-medium text-[var(--text)]">
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
          className="mt-4 rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm font-medium text-rose-900"
          role="alert"
        >
          {error}
        </p>
      ) : null}
      <button
        className="action-primary mt-5 flex min-h-12 w-full items-center justify-center rounded-lg bg-[var(--text)] px-5 py-3 text-sm font-medium text-white transition hover:bg-[#373740] focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[var(--accent)]"
        disabled={submitting}
        type="submit"
      >
        {submitting ? "Validating session…" : "Continue to roles"}
      </button>
    </form>
  );
}
