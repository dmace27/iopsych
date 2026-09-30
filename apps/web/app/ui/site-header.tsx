"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

/** Keep bearer-token candidate pages separate from the internal workspace UI. */
export function SiteHeader() {
  const pathname = usePathname();
  const candidatePage = pathname.startsWith("/candidate/");

  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-6 px-5 py-4 sm:px-8">
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
            <div className="flex items-center gap-1">
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
              <Link
                className="rounded-md px-3 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-100 hover:text-slate-950 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-700"
                href="/sign-in"
              >
                Sign in
              </Link>
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
