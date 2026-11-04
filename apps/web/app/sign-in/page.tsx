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
    <main className="mx-auto max-w-2xl px-5 py-12 sm:px-8" id="main-content">
      <p className="text-xs font-bold uppercase tracking-[0.18em] text-teal-800">
        Internal access
      </p>
      <h1 className="mt-2 text-4xl font-bold tracking-tight text-slate-950">
        Sign in to Role studio
      </h1>
      <p className="mt-4 max-w-xl text-base leading-7 text-slate-600">
        {localLogin
          ? "Local synthetic demonstration only. Choose one of the two seeded accounts; these tenants are isolated and contain no real participant data."
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
            typeof parameters.error === "string" ? parameters.error : undefined
          }
        />
      </div>
    </main>
  );
}
