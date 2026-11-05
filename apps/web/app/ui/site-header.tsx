"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { ApiClientError, getCurrentUser } from "../../lib/api-client";
import type { CurrentUser } from "../../lib/contracts";
import { isInternalAccountPath, signInHref } from "../../lib/safe-return-to";
import { StudioIcon } from "./studio-icon";

/** Keep bearer-token candidate pages separate from the internal workspace UI. */
export function SiteHeader() {
  const pathname = usePathname();
  const candidatePage =
    pathname === "/candidate" || pathname.startsWith("/candidate/");
  const workspacePage = isInternalAccountPath(pathname);
  const section = pathname.includes("/invites")
    ? "Invitations"
    : pathname.includes("/reports")
      ? "Reports"
      : pathname === "/privacy"
        ? "Privacy"
        : pathname === "/accounts"
          ? "Accounts"
          : pathname === "/roles"
            ? "Roles"
            : "Role profile";

  return (
    <>
      <header
        className="site-header"
        data-mode={workspacePage ? "workspace" : "public"}
      >
        <div className="site-header-inner">
          {candidatePage ? (
            <div className="site-brand">
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
            <Link className="site-brand" href="/roles">
              <BrandMark />
              <span>
                <span className="block text-sm font-bold tracking-tight text-slate-950">
                  IOPsych
                </span>
                <span className="block text-xs text-slate-500">
                  Role studio
                </span>
              </span>
            </Link>
          )}
          {candidatePage ? (
            <span className="text-xs font-semibold text-slate-500">
              Secure invitation
            </span>
          ) : (
            <nav aria-label="Primary navigation">
              <div className="site-navigation">
                {workspacePage ? (
                  <span className="site-nav-label" aria-hidden="true">
                    Workspace
                  </span>
                ) : null}
                <Link
                  className="site-nav-link"
                  href="/roles"
                  aria-current={
                    pathname === "/roles"
                      ? "page"
                      : pathname.startsWith("/roles/") ||
                          pathname.startsWith("/reports/")
                        ? "location"
                        : undefined
                  }
                >
                  <StudioIcon name="roles" />
                  Roles
                </Link>
                <Link
                  className="site-nav-link"
                  href="/privacy"
                  aria-current={pathname === "/privacy" ? "page" : undefined}
                >
                  <StudioIcon name="privacy" />
                  Privacy
                </Link>
                {isInternalAccountPath(pathname) ? (
                  <AccountControls key={pathname} pathname={pathname} />
                ) : (
                  <Link
                    href="/sign-in"
                    className="site-nav-link"
                    aria-current={pathname === "/sign-in" ? "page" : undefined}
                  >
                    Sign in
                  </Link>
                )}
              </div>
            </nav>
          )}
        </div>
      </header>
      {workspacePage ? (
        <div className="workspace-topbar">
          <div className="workspace-breadcrumb">
            <span>Role studio</span>
            <span aria-hidden="true">/</span>
            <span>{section}</span>
          </div>
          <span className="workspace-private">
            <StudioIcon name="lock" />
            Private workspace
          </span>
        </div>
      ) : null}
    </>
  );
}

function BrandMark() {
  return (
    <span aria-hidden="true" className="brand-mark">
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
    <>
      {account?.role === "admin" ? (
        <Link
          href="/accounts"
          className="site-nav-link"
          aria-current={pathname === "/accounts" ? "page" : undefined}
        >
          <StudioIcon name="accounts" />
          Accounts
        </Link>
      ) : null}
      <div className="site-account">
        {status === "loading" ? (
          <span role="status">Checking session…</span>
        ) : null}
        {account ? (
          <div className="site-account-identity">
            <span className="account-avatar" aria-hidden="true">
              {account.name
                .split(" ")
                .map((part) => part[0])
                .slice(0, 2)
                .join("")}
            </span>
            <p className="font-medium text-slate-900">
              {account.name} · {account.role.replaceAll("_", " ")}
            </p>
            <details className="account-organization">
              <summary>
                {account.organization_name ?? "Organization details"}
              </summary>
              <p className="text-xs">Organization: {account.organization_id}</p>
            </details>
          </div>
        ) : null}
        {status === "expired" ? (
          <span role="status">
            Your session has expired or you are signed out.{" "}
            <Link
              href={signInHref(pathname)}
              referrerPolicy="no-referrer"
              className="site-nav-link underline"
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
            className="action-secondary"
          >
            {signingOut ? "Signing out…" : "Sign out"}
          </button>
        ) : null}
        {signOutError && status !== "expired" ? (
          <p role="alert" className="w-full text-red-800">
            Sign out failed. Your session may still be active. Try again.
          </p>
        ) : null}
      </div>
    </>
  );
}
