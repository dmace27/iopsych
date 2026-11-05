import type { Metadata } from "next";

import { safeReturnTo } from "../../lib/safe-return-to";

import { SignInForm } from "./sign-in-form";

export const metadata: Metadata = {
  title: "Sign in",
};

/** Offer provider login while retaining explicitly enabled synthetic access. */
export default async function SignInPage({
  searchParams,
}: {
  searchParams: Promise<{
    returnTo?: string | string[];
    error?: string | string[];
  }>;
}) {
  const parameters = await searchParams;
  const returnTo = safeReturnTo(parameters.returnTo);
  const localLogin =
    process.env.LOCAL_LOGIN_ENABLED === "true" &&
    process.env.NODE_ENV === "development";
  return (
    <main
      className="signin-shell mx-auto grid min-h-[calc(100svh-5rem)] max-w-7xl gap-10 px-5 py-6 sm:px-8 lg:grid-cols-[1.05fr_1fr] lg:gap-16 lg:py-8"
      id="main-content"
    >
      <section
        className="signin-intro relative order-2 flex flex-col justify-between overflow-hidden rounded-2xl bg-[#24242c] px-7 py-8 text-white sm:px-10 sm:py-10 lg:order-1 lg:min-h-[600px]"
        aria-labelledby="signin-intro-title"
      >
        <div className="flex items-center gap-3 text-sm text-white/65">
          <span
            aria-hidden="true"
            className="grid size-8 place-items-center rounded-lg border border-white/20 text-xs font-medium text-white"
          >
            IO
          </span>
          A workspace for considered decisions
        </div>
        <div className="py-12 lg:py-16">
          <p className="mb-5 text-xs font-medium tracking-[0.12em] text-[#c7bff2]">
            ROLE STUDIO
          </p>
          <h2
            id="signin-intro-title"
            className="max-w-md text-4xl font-medium leading-[1.12] tracking-[-0.045em] sm:text-5xl"
          >
            A clearer picture of the work ahead.
          </h2>
          <p className="mt-6 max-w-sm text-sm leading-7 text-white/65">
            Bring role requirements, work preferences, and supporting evidence
            into one thoughtful review.
          </p>
        </div>
        <ol
          className="grid gap-5 border-t border-white/15 pt-7 text-sm sm:grid-cols-3 lg:grid-cols-1 lg:gap-4"
          aria-label="How Role studio works"
        >
          {[
            [
              "01",
              "Define the role",
              "Start with the work and its requirements.",
            ],
            ["02", "Understand preferences", "Invite a consented assessment."],
            ["03", "Review the evidence", "Keep human judgment at the center."],
          ].map(([number, title, description]) => (
            <li key={number} className="flex gap-4">
              <span
                aria-hidden="true"
                className="pt-0.5 text-xs tabular-nums text-[#b7addf]"
              >
                {number}
              </span>
              <span>
                <span className="block font-medium">{title}</span>
                <span className="mt-1 block text-xs leading-5 text-white/55">
                  {description}
                </span>
              </span>
            </li>
          ))}
        </ol>
      </section>
      <section
        className="signin-access order-1 flex min-w-0 items-center py-4 sm:py-8 lg:order-2 lg:py-12"
        aria-labelledby="signin-title"
      >
        <div className="mx-auto w-full max-w-[390px]">
          <p className="mb-4 text-xs font-medium tracking-wide text-[var(--muted)]">
            YOUR WORKSPACE
          </p>
          <h1
            id="signin-title"
            className="text-[30px] font-medium leading-tight tracking-[-0.04em] text-[var(--text)]"
          >
            Sign in to Role studio
          </h1>
          <p className="mt-3 text-sm leading-6 text-[var(--muted)]">
            {localLogin
              ? "Choose a demo account to explore the workspace."
              : "Sign in through your organization’s identity provider to access your workspace."}
          </p>
          <div className="mt-8">
            <SignInForm
              localLogin={localLogin}
              tokenLogin={
                process.env.ENABLE_TOKEN_SIGN_IN === "true" &&
                process.env.NODE_ENV !== "production"
              }
              returnTo={returnTo}
              providerError={
                typeof parameters.error === "string"
                  ? parameters.error
                  : undefined
              }
            />
          </div>
          {localLogin ? (
            <p className="mt-7 border-t border-[var(--border)] pt-5 text-xs leading-6 text-[var(--muted)]">
              Local synthetic demonstration only. Choose one of the two seeded
              accounts; these tenants are isolated and contain no real
              participant data.
            </p>
          ) : null}
          <p className="mt-7 text-xs leading-6 text-[var(--muted)]">
            Role profiles support evidence-seeking conversations. Employment
            decisions remain human reviewed.
          </p>
        </div>
      </section>
    </main>
  );
}
