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
import { StudioIcon } from "../ui/studio-icon";
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
  const searchInput = useRef<HTMLInputElement>(null);
  const createButton = useRef<HTMLButtonElement>(null);
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [showCreate, setShowCreate] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [announcement, setAnnouncement] = useState("");
  const [query, setQuery] = useState("");
  const [roleFilter, setRoleFilter] = useState<Role["status"] | "all">("all");
  const [sort, setSort] = useState("newest");
  const visibleRoles =
    state.status === "ready"
      ? state.roles
          .filter(
            (role) =>
              (roleFilter === "all" || role.status === roleFilter) &&
              `${role.title} ${role.department} ${role.location}`
                .toLocaleLowerCase()
                .includes(query.trim().toLocaleLowerCase()),
          )
          .sort((a, b) =>
            sort === "title"
              ? a.title.localeCompare(b.title)
              : sort === "oldest"
                ? Date.parse(a.created_at) - Date.parse(b.created_at)
                : Date.parse(b.created_at) - Date.parse(a.created_at),
          )
      : [];

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
      <div className="roles-page-header">
        <div>
          <p className="workspace-eyebrow">Your workspace</p>
          <h1 className="workspace-title text-2xl font-semibold tracking-tight text-slate-900 sm:text-[28px]">
            Roles
          </h1>
          <p>
            Define role requirements and review evidence before human approval.
          </p>
        </div>
        {state.status === "ready" && canEditRoles(state.user.role) ? (
          <button
            ref={createButton}
            aria-expanded={showCreate}
            aria-controls="create-role-form"
            className="action-primary"
            onClick={() => setShowCreate((visible) => !visible)}
            type="button"
          >
            <StudioIcon name="plus" />
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
              <span className="mt-1 block text-xs font-normal leading-5 text-slate-600">
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
                className="action-primary min-h-11 rounded-md bg-[var(--accent,#0f766e)] px-5 py-2.5 text-sm font-semibold text-white hover:bg-teal-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-700 focus-visible:ring-offset-2"
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

      <section aria-labelledby="role-list-title" className="roles-library">
        <h2 className="sr-only" id="role-list-title">
          Organization roles
        </h2>
        {state.status === "ready" ? (
          <div className="roles-toolbar">
            <div
              className="roles-view-tabs"
              role="group"
              aria-label="Filter roles by status"
            >
              {(
                [
                  ["all", "All roles"],
                  ["active", "Active"],
                  ["draft", "Drafts"],
                  ["archived", "Archived"],
                ] as const
              ).map(([value, label]) => (
                <button
                  type="button"
                  key={value}
                  aria-pressed={roleFilter === value}
                  onClick={() => setRoleFilter(value)}
                >
                  {label}
                  <span className="roles-tab-count" aria-hidden="true">
                    {value === "all"
                      ? state.roles.length
                      : state.roles.filter((role) => role.status === value)
                          .length}
                  </span>
                </button>
              ))}
            </div>
            <div className="roles-toolbar-actions">
              <label className="roles-search">
                <span className="sr-only">Search roles</span>
                <StudioIcon name="search" />
                <input
                  ref={searchInput}
                  type="search"
                  placeholder="Search roles…"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                />
              </label>
              <label>
                <span className="sr-only">Sort roles</span>
                <select
                  className="roles-sort"
                  value={sort}
                  onChange={(event) => setSort(event.target.value)}
                >
                  <option value="newest">Newest first</option>
                  <option value="oldest">Oldest first</option>
                  <option value="title">Title A–Z</option>
                </select>
              </label>
            </div>
          </div>
        ) : null}

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
        {state.status === "ready" &&
        state.roles.length > 0 &&
        visibleRoles.length === 0 ? (
          <EmptyState
            title="No matching roles"
            description="Try a different title, department, location, or status."
          >
            <button
              className="action-secondary"
              type="button"
              onClick={() => {
                setQuery("");
                setRoleFilter("all");
                searchInput.current?.focus();
              }}
            >
              Clear filters
            </button>
          </EmptyState>
        ) : null}
        {state.status === "ready" && visibleRoles.length > 0 ? (
          <div className="roles-table">
            <div className="roles-table-heading" aria-hidden="true">
              <span>Role</span>
              <span>Status</span>
              <span>Created</span>
              <span />
            </div>
            <ul className="record-list divide-y divide-slate-200 bg-white">
              {visibleRoles.map((role) => (
                <li key={role.id}>
                  <Link className="role-record" href={`/roles/${role.id}`}>
                    <div className="role-record-title">
                      <span className="role-record-mark" aria-hidden="true">
                        <StudioIcon name="roles" />
                      </span>
                      <div className="min-w-0">
                        <h3 className="break-words text-base font-semibold text-slate-900 group-hover:text-teal-900">
                          {role.title}
                        </h3>
                        <p className="mt-1 break-words text-sm text-slate-600">
                          {role.department} · {role.location}
                        </p>
                      </div>
                    </div>
                    <div>
                      <StatusBadge status={role.status} />
                    </div>
                    <span className="role-record-date">
                      Created {formatDate(role.created_at)}
                    </span>
                    <span aria-hidden="true" className="role-record-arrow">
                      <StudioIcon name="arrow" />
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
        {state.status === "ready" && state.roles.length > 0 ? (
          <p className="roles-list-caption" aria-live="polite">
            {visibleRoles.length} of {state.roles.length}{" "}
            {state.roles.length === 1 ? "role" : "roles"}
          </p>
        ) : null}
      </section>

      <aside className="roles-principle">
        <StudioIcon name="privacy" />
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
