"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { getCurrentUser } from "../../lib/api-client";
import type { CurrentUser } from "../../lib/contracts";

/** Refresh database-backed account context on navigation and provide sign-out. */
export function AccountMenu() {
  const pathname = usePathname();
  const router = useRouter();
  const [account, setAccount] = useState<CurrentUser | null>(null);
  const [error, setError] = useState(false);
  useEffect(() => {
    let active = true;
    const expired = () => setAccount(null);
    window.addEventListener("iopsych:session-expired", expired);
    getCurrentUser()
      .then((user) => {
        if (active) setAccount(user);
      })
      .catch(() => {
        if (active) setAccount(null);
      });
    return () => {
      active = false;
      window.removeEventListener("iopsych:session-expired", expired);
    };
  }, [pathname]);

  async function signOut() {
    setError(false);
    try {
      const result = await fetch("/api/session", { method: "DELETE" });
      if (!result.ok) throw new Error("Sign-out failed");
      setAccount(null);
      router.replace("/sign-in");
      router.refresh();
    } catch {
      setError(true);
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-3 text-sm">
      {account ? (
        <>
          <span>
            {account.name} · {account.role.replaceAll("_", " ")}
            <span className="block text-xs text-slate-500">
              Organization:{" "}
              {account.organization_name ?? account.organization_id}
            </span>
          </span>
          {account.role === "admin" ? (
            <Link href="/accounts">Accounts</Link>
          ) : null}
          <button type="button" onClick={signOut}>
            Sign out
          </button>
        </>
      ) : (
        <Link href={`/sign-in?${new URLSearchParams({ returnTo: pathname })}`}>
          Sign in
        </Link>
      )}
      {error ? <span role="alert">Sign-out failed. Try again.</span> : null}
    </div>
  );
}
