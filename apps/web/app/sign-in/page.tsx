import type { Metadata } from "next";

import { SignInForm } from "./sign-in-form";

export const metadata: Metadata = {
  title: "Sign in",
};

/** Render the provider-token exchange used to establish the secure session. */
export default function SignInPage() {
  return (
    <main className="mx-auto max-w-2xl px-5 py-12 sm:px-8" id="main-content">
      <p className="text-xs font-bold uppercase tracking-[0.18em] text-teal-800">
        Internal access
      </p>
      <h1 className="mt-2 text-4xl font-bold tracking-tight text-slate-950">
        Sign in to Role studio
      </h1>
      <p className="mt-4 max-w-xl text-base leading-7 text-slate-600">
        Use an internal-user access token issued by the configured identity
        provider. The token is exchanged for a secure, HTTP-only browser session
        and is never stored in browser JavaScript.
      </p>
      <div className="mt-8">
        <SignInForm />
      </div>
    </main>
  );
}
