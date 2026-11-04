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
  const createButton = useRef<HTMLButtonElement>(null);
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
    <main
      className="workspace-shell mx-auto max-w-6xl px-4 py-6 sm:px-8"
      id="main-content"
    >
      <div aria-live="polite" className="sr-only">
        {announcement}
      </div>
      <div className="flex flex-col justify-between gap-4 border-b border-slate-200 pb-5 sm:flex-row sm:items-center">
        <div>
          <h1 className="workspace-title text-2xl font-semibold tracking-tight text-slate-900 sm:text-[28px]">
            Roles
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
            Define role requirements and review evidence before human approval.
          </p>
        </div>
        {state.status === "ready" && canEditRoles(state.user.role) ? (
          <button
            ref={createButton}
            aria-expanded={showCreate}
            aria-controls="create-role-form"
            className="action-primary inline-flex min-h-11 items-center justify-center rounded-md bg-teal-700 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-teal-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-700 focus-visible:ring-offset-2"
            onClick={() => setShowCreate((visible) => !visible)}
            type="button"
          >
            {showCreate ? "Close form" : "Create role"}
          </button>
        ) : null}
      </div>

      {showCreate && state.status === "ready" ? (
        <section
          id="create-role-form"
          aria-labelledby="create-role-title"
          className="surface mt-6 rounded-lg border border-slate-200 bg-white p-4 sm:p-6"
        >
          <div className="max-w-3xl">
            <h2
              className="text-lg font-semibold text-slate-900"
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
            <label className="field-label block text-sm font-semibold text-slate-800">
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
            <label className="field-label block text-sm font-semibold text-slate-800">
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
            <label className="field-label block text-sm font-semibold text-slate-800">
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
            <label className="field-label block text-sm font-semibold text-slate-800 sm:col-span-2">
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
                className="action-primary min-h-11 rounded-md bg-teal-700 px-5 py-2.5 text-sm font-semibold text-white hover:bg-teal-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-700 focus-visible:ring-offset-2"
                disabled={submitting}
                type="submit"
              >
                {submitting ? "Creating draft…" : "Create draft role"}
              </button>
              <button
                className="action-secondary min-h-11 rounded-md border border-slate-300 bg-white px-5 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-700 focus-visible:ring-offset-2"
                disabled={submitting}
                onClick={() => {
                  setShowCreate(false);
                  createButton.current?.focus();
                }}
                type="button"
              >
                Cancel
              </button>
            </div>
          </form>
        </section>
      ) : null}

      <section aria-labelledby="role-list-title" className="mt-6">
        <div className="mb-3 flex items-center justify-between gap-4">
          <h2
            className="text-base font-semibold text-slate-900"
            id="role-list-title"
          >
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
          <ul className="record-list surface divide-y divide-slate-200 overflow-hidden rounded-lg border border-slate-200 bg-white">
            {state.roles.map((role) => (
              <li key={role.id}>
                <Link
                  className="record-row group grid min-h-11 gap-3 px-4 py-4 transition hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-teal-700 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center"
                  href={`/roles/${role.id}`}
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0">
                      <h3 className="break-words text-base font-semibold text-slate-900 group-hover:text-teal-900">
                        {role.title}
                      </h3>
                      <p className="mt-1 break-words text-sm text-slate-600">
                        {role.department} · {role.location}
                      </p>
                    </div>
                    <StatusBadge status={role.status} />
                  </div>
                  <div className="flex items-center gap-4 text-xs text-slate-600">
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

      <aside className="mt-6 border-t border-slate-200 py-4 text-slate-700">
        <div>
          <p className="text-sm font-semibold">
            Human judgment stays in the loop.
          </p>
          <p className="mt-1 text-sm leading-6 text-slate-600">
            Profiles describe role demands. They do not rank candidates or make
            employment decisions.
          </p>
        </div>
      </aside>
    </main>
  );
}
