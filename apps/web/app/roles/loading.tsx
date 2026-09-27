import { LoadingState } from "../ui/workspace-states";

/** Provide an immediate accessible navigation fallback for the roles route. */
export default function RolesLoading() {
  return (
    <main className="mx-auto max-w-7xl px-5 py-10 sm:px-8" id="main-content">
      <h1 className="text-3xl font-bold tracking-tight text-slate-950">
        Roles
      </h1>
      <div className="mt-8">
        <LoadingState label="Loading roles" />
      </div>
    </main>
  );
}
