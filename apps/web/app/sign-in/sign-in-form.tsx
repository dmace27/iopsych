import { safeReturnTo } from "../../lib/return-to";

/** Use a full navigation so authentication and credentials stay with Auth0. */
export function SignInForm({
  returnTo,
  error,
}: {
  returnTo?: string;
  error?: string;
}) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
      {error ? (
        <p role="alert" className="mb-4 text-rose-900">
          {error === "configuration"
            ? "Sign-in is not configured. Contact your administrator."
            : "Sign-in could not be completed. Try again or ask your administrator to check your access."}
        </p>
      ) : null}
      <a
        className="inline-block rounded-xl bg-teal-800 px-5 py-3 font-bold text-white"
        href={`/api/auth/login?${new URLSearchParams({ returnTo: safeReturnTo(returnTo) })}`}
      >
        Sign in with Auth0
      </a>
      <p className="mt-4 text-sm text-slate-600">
        Use the account provided by your administrator. Your organization and
        permissions are assigned by your organization.
      </p>
    </div>
  );
}
