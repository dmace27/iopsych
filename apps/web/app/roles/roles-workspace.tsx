"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import {
  ApiClientError,
  createRole,
  getCurrentUser,
  getRoles,
} from "../../lib/api-client";
import type { CurrentUser, Role, RoleCreateInput } from "../../lib/contracts";
import { canEditRoles, formatDate } from "../../lib/role-ui";
import { StatusBadge } from "../ui/status-badge";
import { EmptyState, ErrorState, LoadingState } from "../ui/workspace-states";

type LoadState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; roles: Role[]; user: CurrentUser };

/** Translate API failures into useful workspace-level guidance. */
function errorMessage(error: unknown): string {
  if (error instanceof ApiClientError && error.status === 401) {
    return "Your internal session is missing or expired. Sign in again, then retry.";
  }
  return error instanceof Error
    ? error.message
    : "The role workspace could not be loaded.";
}

/** Interactive list and role-creation screen for one organization. */
export function RolesWorkspace() {
  const router = useRouter();
  const titleInput = useRef<HTMLInputElement>(null);
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [showCreate, setShowCreate] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [announcement, setAnnouncement] = useState("");

  /** Reload after an explicit retry and expose progress immediately. */
  async function load() {
    setState({ status: "loading" });
    try {
      const [roles, user] = await Promise.all([getRoles(), getCurrentUser()]);
      setState({ status: "ready", roles, user });
    } catch (error) {
      setState({ status: "error", message: errorMessage(error) });
    }
  }

  useEffect(() => {
    // Ignore an in-flight response after unmount so it cannot update stale UI.
    let active = true;
    void Promise.all([getRoles(), getCurrentUser()])
      .then(([roles, user]) => {
        if (active) setState({ status: "ready", roles, user });
      })
      .catch((error: unknown) => {
        if (active) setState({ status: "error", message: errorMessage(error) });
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (showCreate) titleInput.current?.focus();
  }, [showCreate]);

  async function handleCreate(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setFormError(null);
    const data = new FormData(event.currentTarget);
    const input: RoleCreateInput = {
      title: String(data.get("title") ?? "").trim(),
      department: String(data.get("department") ?? "").trim(),
      location: String(data.get("location") ?? "").trim(),
      job_description: String(data.get("job_description") ?? "").trim(),
    };
    try {
      const role = await createRole(input);
      setAnnouncement(`${role.title} was created as a draft.`);
      router.push(`/roles/${role.id}`);
    } catch (error) {
      setFormError(errorMessage(error));
      setSubmitting(false);
    }
  }

  return (
    <main className="mx-auto max-w-7xl px-5 py-10 sm:px-8" id="main-content">
      <div aria-live="polite" className="sr-only">
        {announcement}
      </div>
      <div className="flex flex-col justify-between gap-5 border-b border-slate-300 pb-8 sm:flex-row sm:items-end">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-teal-800">
            Internal workspace
          </p>
          <h1 className="mt-2 text-4xl font-bold tracking-tight text-slate-950">
            Roles
          </h1>
          <p className="mt-3 max-w-2xl text-base leading-7 text-slate-600">
            Define the work, review evidence, and obtain human approval before
            any profile is used downstream.
          </p>
        </div>
        {state.status === "ready" && canEditRoles(state.user.role) ? (
          <button
            aria-expanded={showCreate}
            className="inline-flex min-h-11 items-center justify-center rounded-xl bg-teal-800 px-5 py-2.5 text-sm font-bold text-white shadow-sm transition hover:bg-teal-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-700 focus-visible:ring-offset-2"
            onClick={() => setShowCreate((visible) => !visible)}
            type="button"
          >
            {showCreate ? "Close form" : "Create role"}
          </button>
        ) : null}
      </div>

      {showCreate && state.status === "ready" ? (
        <section
          aria-labelledby="create-role-title"
          className="mt-8 rounded-2xl border border-teal-200 bg-white p-6 shadow-sm sm:p-8"
        >
          <div className="max-w-3xl">
            <p className="text-xs font-bold uppercase tracking-[0.16em] text-teal-800">
              New draft
            </p>
            <h2
              className="mt-2 text-2xl font-bold text-slate-950"
              id="create-role-title"
            >
              Describe the role
            </h2>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              Use role requirements only. Do not include candidate information
              or prior hiring decisions.
            </p>
          </div>
          <form
            className="mt-6 grid gap-5 sm:grid-cols-2"
            onSubmit={handleCreate}
          >
            <label className="block text-sm font-bold text-slate-800">
              Role title
              <input
                autoComplete="off"
                className="field-control mt-2"
                disabled={submitting}
                maxLength={160}
                name="title"
                ref={titleInput}
                required
              />
            </label>
            <label className="block text-sm font-bold text-slate-800">
              Department
              <input
                autoComplete="organization-title"
                className="field-control mt-2"
                disabled={submitting}
                maxLength={160}
                name="department"
                required
              />
            </label>
            <label className="block text-sm font-bold text-slate-800">
              Location
              <input
                autoComplete="off"
                className="field-control mt-2"
                disabled={submitting}
                maxLength={160}
                name="location"
                required
              />
            </label>
            <div className="hidden sm:block" />
            <label className="block text-sm font-bold text-slate-800 sm:col-span-2">
              Job description
              <span className="mt-1 block text-xs font-normal leading-5 text-slate-500">
                This source text anchors every profile evidence excerpt.
              </span>
              <textarea
                className="field-control mt-2 min-h-48 resize-y leading-6"
                disabled={submitting}
                maxLength={100000}
                name="job_description"
                required
              />
            </label>
            {formError ? (
              <p
                className="text-sm font-semibold text-rose-800 sm:col-span-2"
                role="alert"
              >
                {formError}
              </p>
            ) : null}
            <div className="flex flex-wrap gap-3 sm:col-span-2">
              <button
                className="min-h-11 rounded-xl bg-teal-800 px-5 py-2.5 text-sm font-bold text-white hover:bg-teal-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-700 focus-visible:ring-offset-2"
                disabled={submitting}
                type="submit"
              >
                {submitting ? "Creating draft…" : "Create draft role"}
              </button>
              <button
                className="min-h-11 rounded-xl border border-slate-300 bg-white px-5 py-2.5 text-sm font-bold text-slate-700 hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-700 focus-visible:ring-offset-2"
                disabled={submitting}
                onClick={() => setShowCreate(false)}
                type="button"
              >
                Cancel
              </button>
            </div>
          </form>
        </section>
      ) : null}

      <section aria-labelledby="role-list-title" className="mt-9">
        <div className="mb-5 flex items-center justify-between gap-4">
          <h2 className="text-xl font-bold text-slate-950" id="role-list-title">
            Organization roles
          </h2>
          {state.status === "ready" ? (
            <span className="text-sm text-slate-500">
              {state.roles.length} {state.roles.length === 1 ? "role" : "roles"}
            </span>
          ) : null}
        </div>

        {state.status === "loading" ? (
          <LoadingState label="Loading roles" />
        ) : null}
        {state.status === "error" ? (
          <ErrorState
            message={state.message}
            onRetry={() => void load()}
            title="Roles are unavailable"
          />
        ) : null}
        {state.status === "ready" && state.roles.length === 0 ? (
          <EmptyState
            description={
              canEditRoles(state.user.role)
                ? "Create the first role to begin a human-reviewed profile."
                : "A recruiter has not created a role for this organization yet."
            }
            title="No roles yet"
          />
        ) : null}
        {state.status === "ready" && state.roles.length > 0 ? (
          <ul className="grid gap-4 lg:grid-cols-2">
            {state.roles.map((role) => (
              <li key={role.id}>
                <Link
                  className="group block h-full rounded-2xl border border-slate-200 bg-white p-6 shadow-sm transition hover:-translate-y-0.5 hover:border-teal-300 hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-700 focus-visible:ring-offset-2"
                  href={`/roles/${role.id}`}
                >
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <p className="text-xs font-bold uppercase tracking-[0.14em] text-slate-500">
                        {role.department}
                      </p>
                      <h3 className="mt-2 text-xl font-bold tracking-tight text-slate-950 group-hover:text-teal-900">
                        {role.title}
                      </h3>
                    </div>
                    <StatusBadge status={role.status} />
                  </div>
                  <div className="mt-6 flex flex-wrap items-center gap-x-5 gap-y-2 border-t border-slate-100 pt-4 text-sm text-slate-600">
                    <span>{role.location}</span>
                    <span aria-hidden="true" className="text-slate-300">
                      •
                    </span>
                    <span>Created {formatDate(role.created_at)}</span>
                    <span
                      aria-hidden="true"
                      className="ml-auto text-lg text-teal-700"
                    >
                      →
                    </span>
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        ) : null}
      </section>

      <aside className="mt-10 rounded-2xl bg-slate-900 px-6 py-5 text-slate-100 sm:flex sm:items-center sm:justify-between sm:gap-8">
        <div>
          <p className="font-bold">Human judgment stays in the loop.</p>
          <p className="mt-1 text-sm leading-6 text-slate-300">
            Profiles describe role demands. They do not rank candidates or make
            employment decisions.
          </p>
        </div>
        <span className="mt-4 inline-flex rounded-full border border-slate-600 px-3 py-1 text-xs font-bold sm:mt-0">
          Responsible-use pilot
        </span>
      </aside>
    </main>
  );
}
