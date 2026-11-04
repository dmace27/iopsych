"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { ApiClientError, getCurrentUser } from "../../lib/api-client";
import type { CurrentUser } from "../../lib/contracts";
import { isInternalAccountPath, signInHref } from "../../lib/safe-return-to";

/** Keep bearer-token candidate pages separate from the internal workspace UI. */
export function SiteHeader() {
  const pathname = usePathname();
  const candidatePage =
    pathname === "/candidate" || pathname.startsWith("/candidate/");

  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-6 px-5 py-4 sm:px-8">
        {candidatePage ? (
          <div className="inline-flex items-center gap-3">
            <BrandMark />
            <span>
              <span className="block text-sm font-bold tracking-tight text-slate-950">
                IOPsych
              </span>
              <span className="block text-xs text-slate-500">
                Candidate assessment
              </span>
            </span>
          </div>
        ) : (
          <Link
            className="group inline-flex items-center gap-3 rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-700 focus-visible:ring-offset-4"
            href="/roles"
          >
            <BrandMark />
            <span>
              <span className="block text-sm font-bold tracking-tight text-slate-950">
                IOPsych
              </span>
              <span className="block text-xs text-slate-500">Role studio</span>
            </span>
          </Link>
        )}
        {candidatePage ? (
          <span className="text-xs font-semibold text-slate-500">
            Secure invitation
          </span>
        ) : (
          <nav aria-label="Primary navigation">
            <div className="flex flex-wrap items-center gap-1">
              <Link
                className="rounded-md px-3 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-100 hover:text-slate-950 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-700"
                href="/roles"
              >
                Roles
              </Link>
              <Link
                className="rounded-md px-3 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-100 hover:text-slate-950 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-700"
                href="/privacy"
              >
                Privacy
              </Link>
              {isInternalAccountPath(pathname) ? (
                <AccountControls key={pathname} pathname={pathname} />
              ) : (
                <Link
                  href="/sign-in"
                  className="rounded-md px-3 py-2 text-sm font-semibold text-slate-700"
                >
                  Sign in
                </Link>
              )}
            </div>
          </nav>
        )}
      </div>
    </header>
  );
}

function BrandMark() {
  return (
    <span
      aria-hidden="true"
      className="grid size-9 place-items-center rounded-lg bg-teal-800 text-sm font-bold text-white shadow-sm"
    >
      IO
    </span>
  );
}

function AccountControls({ pathname }: { pathname: string }) {
  const router = useRouter();
  const [account, setAccount] = useState<CurrentUser | null>(null);
  const [status, setStatus] = useState<
    "loading" | "ready" | "expired" | "error"
  >("loading");
  const [signingOut, setSigningOut] = useState(false);
  const [signOutError, setSignOutError] = useState(false);
  const generation = useRef(0);
  const signingOutRef = useRef(false);

  useEffect(() => {
    let active = true;
    async function refreshAccount() {
      if (signingOutRef.current) return;
      const request = ++generation.current;
      try {
        const user = await getCurrentUser();
        if (!active || request !== generation.current) return;
        setAccount(user);
        setStatus("ready");
      } catch (error) {
        if (!active || request !== generation.current) return;
        setAccount(null);
        setStatus(
          error instanceof ApiClientError && error.status === 401
            ? "expired"
            : "error",
        );
      }
    }
    void refreshAccount();
    window.addEventListener("focus", refreshAccount);
    const timer = window.setInterval(refreshAccount, 60_000);
    return () => {
      active = false;
      window.removeEventListener("focus", refreshAccount);
      window.clearInterval(timer);
    };
  }, []);

  async function signOut() {
    signingOutRef.current = true;
    ++generation.current;
    setSigningOut(true);
    setSignOutError(false);
    try {
      const response = await fetch("/api/session", {
        method: "DELETE",
        referrerPolicy: "no-referrer",
      });
      if (!response.ok) throw new Error("Sign out failed");
      setAccount(null);
      setStatus("expired");
      router.replace(signInHref(pathname));
      router.refresh();
    } catch {
      setSignOutError(true);
      signingOutRef.current = false;
      setSigningOut(false);
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-3 text-sm text-slate-700">
      {status === "loading" ? (
        <span role="status">Checking session…</span>
      ) : null}
      {account?.role === "admin" ? (
        <Link
          href="/accounts"
          className="rounded-md px-3 py-2 font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-700"
        >
          Accounts
        </Link>
      ) : null}
      {account ? (
        <div className="max-w-sm break-words">
          <p className="font-semibold">
            {account.name} · {account.role.replaceAll("_", " ")}
          </p>
          <p className="text-xs">Organization: {account.organization_id}</p>
        </div>
      ) : null}
      {status === "expired" ? (
        <span role="status">
          Your session has expired or you are signed out.{" "}
          <Link
            href={signInHref(pathname)}
            referrerPolicy="no-referrer"
            className="font-semibold underline"
          >
            Sign in to continue
          </Link>
        </span>
      ) : null}
      {status === "error" ? (
        <span role="status">
          Account details unavailable. Refocus this window to retry.
        </span>
      ) : null}
      {status === "ready" || status === "error" ? (
        <button
          type="button"
          onClick={signOut}
          disabled={signingOut}
          className="rounded-md px-3 py-2 font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-700"
        >
          {signingOut ? "Signing out…" : "Sign out"}
        </button>
      ) : null}
      {signOutError ? (
        <p role="alert">
          Sign out failed. Your session may still be active. Try again.
        </p>
      ) : null}
    </div>
  );
}
