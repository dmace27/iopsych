import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "Role studio · IOPsych",
    template: "%s · IOPsych",
  },
  description:
    "Human-reviewed role profiles for evidence-seeking interview preparation.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <a className="skip-link" href="#main-content">
          Skip to main content
        </a>
        <header className="border-b border-slate-200 bg-white">
          <div className="mx-auto flex max-w-7xl items-center justify-between gap-6 px-5 py-4 sm:px-8">
            <Link
              className="group inline-flex items-center gap-3 rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-700 focus-visible:ring-offset-4"
              href="/roles"
            >
              <span
                aria-hidden="true"
                className="grid size-9 place-items-center rounded-lg bg-teal-800 text-sm font-bold text-white shadow-sm"
              >
                IO
              </span>
              <span>
                <span className="block text-sm font-bold tracking-tight text-slate-950">
                  IOPsych
                </span>
                <span className="block text-xs text-slate-500">
                  Role studio
                </span>
              </span>
            </Link>
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
                  href="/sign-in"
                >
                  Sign in
                </Link>
              </div>
            </nav>
          </div>
        </header>
        {children}
      </body>
    </html>
  );
}
