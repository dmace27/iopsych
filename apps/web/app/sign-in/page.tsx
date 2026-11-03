import type { Metadata } from "next";

import { SignInForm } from "./sign-in-form";

export const metadata: Metadata = {
  title: "Sign in",
};

/** Render provider login and safe, actionable session-recovery feedback. */
export default async function SignInPage({
  searchParams,
}: {
  searchParams: Promise<{ returnTo?: string; error?: string }>;
}) {
  const parameters = await searchParams;
  return (
    <main className="mx-auto max-w-2xl px-5 py-12 sm:px-8" id="main-content">
      <p className="text-xs font-bold uppercase tracking-[0.18em] text-teal-800">
        Internal access
      </p>
      <h1 className="mt-2 text-4xl font-bold tracking-tight text-slate-950">
        Sign in to Role studio
      </h1>
      <p className="mt-4 max-w-xl text-base leading-7 text-slate-600">
        Sign in through your organization’s identity provider to access roles,
        approvals, and reports. If your session expires, sign in again to return
        to your workspace.
      </p>
      <div className="mt-8">
        <SignInForm returnTo={parameters.returnTo} error={parameters.error} />
      </div>
    </main>
  );
}
