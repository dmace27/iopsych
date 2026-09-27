"use client";

import {
  CONSTRUCT_DEFINITIONS_BY_KEY,
  type ConfidenceLevel,
  type ConstructKey,
} from "@iopsych/shared";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import {
  ApiClientError,
  approveRoleProfile,
  createRoleProfile,
  getCurrentUser,
  getRole,
  getRoleProfiles,
  reviseRoleProfile,
} from "../../../lib/api-client";
import type {
  CurrentUser,
  Role,
  RoleConstructRating,
  RoleProfile,
} from "../../../lib/contracts";
import {
  blankConstructs,
  canApproveProfiles,
  canCreateProfiles,
  canEditProfiles,
  formatDate,
  sortProfiles,
} from "../../../lib/role-ui";
import { StatusBadge } from "../../ui/status-badge";
import {
  EmptyState,
  ErrorState,
  LoadingState,
} from "../../ui/workspace-states";

type WorkspaceState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | {
      status: "ready";
      role: Role;
      profiles: RoleProfile[];
      user: CurrentUser;
    };

/** Translate API errors into actionable profile-workspace messages. */
function errorMessage(error: unknown): string {
  if (error instanceof ApiClientError && error.status === 401) {
    return "Your internal session is missing or expired. Sign in again, then retry.";
  }
  return error instanceof Error
    ? error.message
    : "The role profile could not be loaded.";
}

/** Full internal review screen for one role and its version history. */
export function RoleProfileWorkspace({ roleId }: { roleId: string }) {
  const [state, setState] = useState<WorkspaceState>({ status: "loading" });
  const [selectedProfileId, setSelectedProfileId] = useState<string | null>(
    null,
  );
  const [announcement, setAnnouncement] = useState("");
  const [approving, setApproving] = useState(false);
  const [approvalError, setApprovalError] = useState<string | null>(null);
  const [startingReplacement, setStartingReplacement] = useState(false);

  /** Reload after an explicit retry and expose progress immediately. */
  async function load() {
    setState({ status: "loading" });
    try {
      const [role, profiles, user] = await Promise.all([
        getRole(roleId),
        getRoleProfiles(roleId),
        getCurrentUser(),
      ]);
      const ordered = sortProfiles(profiles);
      setState({ status: "ready", role, profiles: ordered, user });
      setSelectedProfileId((current) => current ?? ordered.at(-1)?.id ?? null);
    } catch (error) {
      setState({ status: "error", message: errorMessage(error) });
    }
  }

  useEffect(() => {
    // Fetching inside the asynchronous continuation avoids a synchronous
    // loading-state cascade while still ignoring responses after unmount.
    let active = true;
    void Promise.all([
      getRole(roleId),
      getRoleProfiles(roleId),
      getCurrentUser(),
    ])
      .then(([role, profiles, user]) => {
        if (!active) return;
        const ordered = sortProfiles(profiles);
        setState({ status: "ready", role, profiles: ordered, user });
        setSelectedProfileId(ordered.at(-1)?.id ?? null);
      })
      .catch((error: unknown) => {
        if (active) setState({ status: "error", message: errorMessage(error) });
      });
    return () => {
      active = false;
    };
  }, [roleId]);

  const selectedProfile = useMemo(() => {
    if (state.status !== "ready") return null;
    return (
      state.profiles.find(({ id }) => id === selectedProfileId) ??
      state.profiles.at(-1) ??
      null
    );
  }, [selectedProfileId, state]);

  function handleSaved(profile: RoleProfile) {
    setState((current) => {
      if (current.status !== "ready") return current;
      return {
        ...current,
        profiles: sortProfiles([...current.profiles, profile]),
      };
    });
    setSelectedProfileId(profile.id);
    setStartingReplacement(false);
    setAnnouncement(`Draft version ${profile.version} was saved.`);
    window.scrollTo({ top: 0, behavior: "auto" });
  }

  async function handleApproval(profile: RoleProfile) {
    setApproving(true);
    setApprovalError(null);
    try {
      await approveRoleProfile(roleId, profile.id);
      const [role, profiles] = await Promise.all([
        getRole(roleId),
        getRoleProfiles(roleId),
      ]);
      setState((current) =>
        current.status === "ready"
          ? { ...current, role, profiles: sortProfiles(profiles) }
          : current,
      );
      setAnnouncement(`Version ${profile.version} was approved.`);
    } catch (error) {
      const message = errorMessage(error);
      setApprovalError(message);
      setAnnouncement(`Approval failed. ${message}`);
    } finally {
      setApproving(false);
    }
  }

  if (state.status === "loading") {
    return (
      <main className="mx-auto max-w-7xl px-5 py-10 sm:px-8" id="main-content">
        <LoadingState label="Loading role profile" />
      </main>
    );
  }

  if (state.status === "error") {
    return (
      <main className="mx-auto max-w-7xl px-5 py-10 sm:px-8" id="main-content">
        <Link
          className="text-sm font-bold text-teal-800 hover:underline"
          href="/roles"
        >
          ← Back to roles
        </Link>
        <div className="mt-6">
          <ErrorState
            message={state.message}
            onRetry={() => void load()}
            title="Role profile unavailable"
          />
        </div>
      </main>
    );
  }

  const latest = state.profiles.at(-1) ?? null;
  const editable =
    selectedProfile?.status === "draft" &&
    selectedProfile.id === latest?.id &&
    canEditProfiles(state.user.role) &&
    state.role.status !== "archived";
  const approvable =
    selectedProfile?.status === "draft" &&
    selectedProfile.id === latest?.id &&
    canApproveProfiles(state.user.role) &&
    state.role.status !== "archived";
  const canStartReplacement =
    selectedProfile?.status === "approved" &&
    selectedProfile.id === latest?.id &&
    canCreateProfiles(state.user.role) &&
    state.role.status !== "archived";

  return (
    <main
      className="mx-auto max-w-7xl px-5 py-8 sm:px-8 sm:py-10"
      id="main-content"
    >
      <div aria-atomic="true" aria-live="polite" className="sr-only">
        {announcement}
      </div>
      <Link
        className="rounded text-sm font-bold text-teal-800 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-700"
        href="/roles"
      >
        ← Back to roles
      </Link>

      <header className="mt-6 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
        <div className="flex flex-col justify-between gap-6 md:flex-row md:items-start">
          <div>
            <div className="flex flex-wrap items-center gap-3">
              <p className="text-xs font-bold uppercase tracking-[0.16em] text-teal-800">
                {state.role.department}
              </p>
              <StatusBadge status={state.role.status} />
            </div>
            <h1 className="mt-3 text-3xl font-bold tracking-tight text-slate-950 sm:text-4xl">
              {state.role.title}
            </h1>
            <p className="mt-3 text-sm text-slate-600">
              {state.role.location} · Created{" "}
              {formatDate(state.role.created_at)}
            </p>
          </div>
          <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm">
            <span className="block font-bold text-slate-900">Signed in as</span>
            <span className="text-slate-600">{state.user.name}</span>
            <span className="block text-xs capitalize text-slate-500">
              {state.user.role.replace("_", " ")}
            </span>
          </div>
        </div>
        <details className="mt-6 rounded-xl border border-slate-200 bg-slate-50 p-4">
          <summary className="cursor-pointer font-bold text-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-700">
            Source job description
          </summary>
          <p className="mt-4 whitespace-pre-wrap text-sm leading-7 text-slate-700">
            {state.role.job_description}
          </p>
        </details>
      </header>

      <div className="mt-8 grid gap-8 xl:grid-cols-[16rem_minmax(0,1fr)]">
        <aside aria-labelledby="version-history-title">
          <div className="sticky top-5 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <h2 className="font-bold text-slate-950" id="version-history-title">
              Version history
            </h2>
            {state.profiles.length === 0 ? (
              <p className="mt-3 text-sm leading-6 text-slate-600">
                No profile versions have been created.
              </p>
            ) : (
              <ol className="mt-4 space-y-2">
                {state.profiles.map((profile) => (
                  <li key={profile.id}>
                    <button
                      aria-current={
                        profile.id === selectedProfile?.id ? "true" : undefined
                      }
                      className={`w-full rounded-xl border px-3 py-3 text-left transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-700 ${
                        profile.id === selectedProfile?.id
                          ? "border-teal-300 bg-teal-50"
                          : "border-transparent hover:border-slate-200 hover:bg-slate-50"
                      }`}
                      onClick={() => setSelectedProfileId(profile.id)}
                      type="button"
                    >
                      <span className="flex items-center justify-between gap-2">
                        <span className="text-sm font-bold text-slate-900">
                          Version {profile.version}
                        </span>
                        <StatusBadge status={profile.status} />
                      </span>
                      <span className="mt-1 block text-xs text-slate-500">
                        {formatDate(profile.created_at)}
                      </span>
                    </button>
                  </li>
                ))}
              </ol>
            )}
            <div className="mt-5 border-t border-slate-200 pt-4 text-xs leading-5 text-slate-500">
              Editing a draft creates a new version. Historical ratings are
              never overwritten.
            </div>
          </div>
        </aside>

        <section aria-labelledby="profile-review-title" className="min-w-0">
          <div className="mb-5 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.16em] text-teal-800">
                Human review
              </p>
              <h2
                className="mt-2 text-2xl font-bold tracking-tight text-slate-950"
                id="profile-review-title"
              >
                {selectedProfile
                  ? `Profile version ${selectedProfile.version}`
                  : "Build the role profile"}
              </h2>
            </div>
            {selectedProfile ? (
              <StatusBadge status={selectedProfile.status} />
            ) : null}
          </div>

          {!selectedProfile && !canCreateProfiles(state.user.role) ? (
            <EmptyState
              description="A recruiter must create the first six-construct draft before manager review can begin."
              title="Waiting for a draft"
            />
          ) : null}

          {!selectedProfile && canCreateProfiles(state.user.role) ? (
            <ProfileEditor
              initialConstructs={blankConstructs()}
              mode="create"
              onSaved={handleSaved}
              role={state.role}
            />
          ) : null}

          {selectedProfile && editable ? (
            <ProfileEditor
              key={selectedProfile.id}
              initialConstructs={selectedProfile.constructs}
              mode="revise"
              onSaved={handleSaved}
              profile={selectedProfile}
              role={state.role}
            />
          ) : null}

          {selectedProfile && !editable ? (
            <ReadonlyProfile profile={selectedProfile} />
          ) : null}

          {canStartReplacement && !startingReplacement ? (
            <button
              className="mt-5 min-h-11 rounded-xl border border-teal-700 bg-white px-5 py-2.5 text-sm font-bold text-teal-800 hover:bg-teal-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-700 focus-visible:ring-offset-2"
              onClick={() => setStartingReplacement(true)}
              type="button"
            >
              Start a new draft from version {selectedProfile.version}
            </button>
          ) : null}

          {canStartReplacement && startingReplacement ? (
            <div className="mt-6">
              <ProfileEditor
                initialConstructs={selectedProfile.constructs}
                mode="create"
                nextVersion={selectedProfile.version + 1}
                onSaved={handleSaved}
                role={state.role}
              />
            </div>
          ) : null}

          {approvable && selectedProfile ? (
            <section
              className="mt-6 rounded-2xl border border-emerald-200 bg-emerald-50 p-6"
              aria-labelledby="approval-title"
            >
              <h3
                className="text-lg font-bold text-emerald-950"
                id="approval-title"
              >
                Approval decision
              </h3>
              <p className="mt-2 text-sm leading-6 text-emerald-900">
                Confirm that all six ratings and evidence excerpts reflect the
                role. Approval freezes this version for downstream use.
              </p>
              <button
                className="mt-4 min-h-11 rounded-xl bg-emerald-800 px-5 py-2.5 text-sm font-bold text-white hover:bg-emerald-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-700 focus-visible:ring-offset-2"
                disabled={approving}
                onClick={() => void handleApproval(selectedProfile)}
                type="button"
              >
                {approving
                  ? "Approving version…"
                  : `Approve version ${selectedProfile.version}`}
              </button>
              {approvalError ? (
                <p
                  className="mt-3 text-sm font-semibold text-rose-900"
                  role="alert"
                >
                  {approvalError}
                </p>
              ) : null}
            </section>
          ) : null}

          {selectedProfile?.status === "draft" && !editable && !approvable ? (
            <p className="mt-5 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
              This draft is read-only for your current role.
            </p>
          ) : null}
        </section>
      </div>
    </main>
  );
}

function ProfileEditor({
  role,
  profile,
  initialConstructs,
  mode,
  nextVersion,
  onSaved,
}: {
  role: Role;
  profile?: RoleProfile;
  initialConstructs: RoleConstructRating[];
  mode: "create" | "revise";
  nextVersion?: number;
  onSaved: (profile: RoleProfile) => void;
}) {
  const [constructs, setConstructs] = useState<RoleConstructRating[]>(() =>
    structuredClone(initialConstructs),
  );
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  function updateConstruct(
    key: ConstructKey,
    change: Partial<RoleConstructRating>,
  ) {
    setConstructs((current) =>
      current.map((construct) =>
        construct.key === key ? { ...construct, ...change } : construct,
      ),
    );
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setSaveError(null);
    const cleaned = constructs.map((construct) => ({
      ...construct,
      rationale: construct.rationale.trim(),
      evidence: construct.evidence
        .flatMap((value) => value.split("\n"))
        .map((value) => value.trim())
        .filter(Boolean),
    }));
    try {
      let saved: RoleProfile;
      if (mode === "create") {
        saved = await createRoleProfile(role.id, { constructs: cleaned });
      } else if (profile) {
        saved = await reviseRoleProfile(role.id, profile.id, {
          constructs: cleaned,
        });
      } else {
        throw new Error("A source profile is required to create a revision.");
      }
      setSaving(false);
      onSaved(saved);
    } catch (error) {
      setSaveError(errorMessage(error));
      setSaving(false);
    }
  }

  return (
    <form className="space-y-5" onSubmit={handleSubmit}>
      <p className="rounded-xl border border-sky-200 bg-sky-50 px-4 py-3 text-sm leading-6 text-sky-950">
        Evidence must be copied verbatim from the source job description.
        Ratings describe role behavior on a 1–5 scale; they are not candidate
        scores.
      </p>
      {constructs.map((construct, index) => {
        const definition = CONSTRUCT_DEFINITIONS_BY_KEY[construct.key];
        const fieldPrefix = `${mode}-${construct.key}`;
        return (
          <fieldset
            className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6"
            disabled={saving}
            key={construct.key}
          >
            <legend className="px-1 text-lg font-bold text-slate-950">
              <span className="mr-2 text-sm text-slate-400">{index + 1}/6</span>
              {definition.label}
            </legend>
            <p
              className="mt-1 text-sm leading-6 text-slate-600"
              id={`${fieldPrefix}-prompt`}
            >
              {definition.role_prompt}
            </p>

            <div className="mt-5 grid gap-5 lg:grid-cols-[minmax(0,1fr)_12rem]">
              <div>
                <span className="block text-sm font-bold text-slate-800">
                  Role rating
                </span>
                <div
                  aria-describedby={`${fieldPrefix}-prompt ${fieldPrefix}-scale-help`}
                  className="mt-2 grid grid-cols-5 gap-2"
                >
                  {[1, 2, 3, 4, 5].map((rating) => (
                    <label className="relative" key={rating}>
                      <input
                        checked={construct.rating === rating}
                        className="peer sr-only"
                        name={`${fieldPrefix}-rating`}
                        onChange={() =>
                          updateConstruct(construct.key, {
                            rating: rating as RoleConstructRating["rating"],
                          })
                        }
                        type="radio"
                        value={rating}
                      />
                      <span className="grid min-h-11 place-items-center rounded-lg border border-slate-300 bg-white text-sm font-bold text-slate-700 peer-checked:border-teal-700 peer-checked:bg-teal-50 peer-checked:text-teal-900 peer-focus-visible:ring-2 peer-focus-visible:ring-teal-700 peer-focus-visible:ring-offset-2">
                        {rating}
                      </span>
                    </label>
                  ))}
                </div>
                <span
                  className="mt-1 flex justify-between text-xs text-slate-500"
                  id={`${fieldPrefix}-scale-help`}
                >
                  <span>Low</span>
                  <span>High</span>
                </span>
              </div>
              <label className="block text-sm font-bold text-slate-800">
                Evidence confidence
                <select
                  className="field-control mt-2"
                  onChange={(event) =>
                    updateConstruct(construct.key, {
                      confidence: event.target.value as ConfidenceLevel,
                    })
                  }
                  value={construct.confidence}
                >
                  <option value="low">Low</option>
                  <option value="medium">Medium</option>
                  <option value="high">High</option>
                </select>
              </label>
            </div>

            <label className="mt-5 block text-sm font-bold text-slate-800">
              Review rationale
              <textarea
                className="field-control mt-2 min-h-24 resize-y font-normal leading-6"
                onChange={(event) =>
                  updateConstruct(construct.key, {
                    rationale: event.target.value,
                  })
                }
                required
                value={construct.rationale}
              />
            </label>
            <label className="mt-5 block text-sm font-bold text-slate-800">
              Job-description evidence
              <span className="mt-1 block text-xs font-normal text-slate-500">
                Enter one exact excerpt per line.
              </span>
              <textarea
                className="field-control mt-2 min-h-24 resize-y font-normal leading-6"
                onChange={(event) =>
                  updateConstruct(construct.key, {
                    evidence: [event.target.value],
                  })
                }
                required
                value={construct.evidence.join("\n")}
              />
            </label>
          </fieldset>
        );
      })}

      {saveError ? (
        <p
          className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm font-semibold text-rose-900"
          role="alert"
        >
          {saveError}
        </p>
      ) : null}
      <div className="sticky bottom-4 flex flex-col gap-3 rounded-2xl border border-slate-200 bg-white/95 p-4 shadow-lg backdrop-blur sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm text-slate-600">
          {mode === "create"
            ? `Creates draft version ${nextVersion ?? 1}.`
            : `Saves as version ${(profile?.version ?? 0) + 1}; version ${profile?.version} remains unchanged.`}
        </p>
        <button
          className="min-h-11 shrink-0 rounded-xl bg-teal-800 px-5 py-2.5 text-sm font-bold text-white hover:bg-teal-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-700 focus-visible:ring-offset-2"
          disabled={saving}
          type="submit"
        >
          {saving
            ? "Saving version…"
            : mode === "create"
              ? "Create draft profile"
              : "Save new version"}
        </button>
      </div>
    </form>
  );
}

function ReadonlyProfile({ profile }: { profile: RoleProfile }) {
  return (
    <div className="space-y-4">
      {profile.status === "approved" ? (
        <p className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm leading-6 text-emerald-950">
          Approved versions are frozen. Create a new complete draft to propose
          future changes.
        </p>
      ) : null}
      {profile.constructs.map((construct, index) => {
        const definition = CONSTRUCT_DEFINITIONS_BY_KEY[construct.key];
        return (
          <article
            aria-labelledby={`construct-${profile.id}-${construct.key}`}
            className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6"
            key={construct.key}
          >
            <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-start">
              <div>
                <p className="text-xs font-bold uppercase tracking-[0.14em] text-slate-400">
                  Construct {index + 1} of 6
                </p>
                <h3
                  className="mt-1 text-lg font-bold text-slate-950"
                  id={`construct-${profile.id}-${construct.key}`}
                >
                  {definition.label}
                </h3>
                <p className="mt-1 text-sm leading-6 text-slate-600">
                  {definition.role_prompt}
                </p>
              </div>
              <div className="flex shrink-0 gap-2">
                <span className="rounded-lg bg-teal-50 px-3 py-2 text-sm font-bold text-teal-900">
                  Rating {construct.rating}/5
                </span>
                <span className="rounded-lg bg-slate-100 px-3 py-2 text-sm font-semibold capitalize text-slate-700">
                  {construct.confidence} confidence
                </span>
              </div>
            </div>
            <div className="mt-5 grid gap-5 border-t border-slate-100 pt-5 lg:grid-cols-2">
              <div>
                <h4 className="text-sm font-bold text-slate-800">
                  Review rationale
                </h4>
                <p className="mt-2 text-sm leading-6 text-slate-700">
                  {construct.rationale}
                </p>
              </div>
              <div>
                <h4 className="text-sm font-bold text-slate-800">
                  Source evidence
                </h4>
                <ul className="mt-2 space-y-2">
                  {construct.evidence.map((excerpt, excerptIndex) => (
                    <li
                      className="border-l-2 border-teal-300 pl-3 text-sm leading-6 text-slate-700"
                      key={`${construct.key}-${excerptIndex}`}
                    >
                      “{excerpt}”
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </article>
        );
      })}
    </div>
  );
}
