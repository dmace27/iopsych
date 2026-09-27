import { LoadingState } from "../../ui/workspace-states";

/** Provide an accessible navigation fallback for the profile workspace. */
export default function ProfileLoading() {
  return (
    <main className="mx-auto max-w-7xl px-5 py-10 sm:px-8" id="main-content">
      <p className="text-sm font-bold text-teal-800">Role profile</p>
      <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-950">
        Loading role…
      </h1>
      <div className="mt-8">
        <LoadingState label="Loading role profile" />
      </div>
    </main>
  );
}
