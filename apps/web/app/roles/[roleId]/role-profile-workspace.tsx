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
  extractRoleProfile,
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
import { canManageInvitations } from "../../../lib/invitation-contracts";
import { RoleMaintenance } from "./role-maintenance";
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
  const [extracting, setExtracting] = useState(false);
  const [extractionError, setExtractionError] = useState<string | null>(null);
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

  async function handleExtraction() {
    setExtracting(true);
    setExtractionError(null);
    setAnnouncement("Extracting a structured role profile.");
    try {
      const profile = await extractRoleProfile(roleId);
      handleSaved(profile);
      setAnnouncement(
        `Draft version ${profile.version} was extracted and is ready for human review.`,
      );
    } catch (error) {
      const message = errorMessage(error);
      setExtractionError(message);
      setAnnouncement(`Extraction failed. ${message}`);
    } finally {
      setExtracting(false);
    }
  }

  if (state.status === "loading") {
    return (
      <main
        className="workspace-shell profile-workspace mx-auto max-w-6xl px-4 py-6 sm:px-8"
        id="main-content"
      >
        <LoadingState label="Loading role profile" />
      </main>
    );
  }

  if (state.status === "error") {
    return (
      <main
        className="workspace-shell profile-workspace mx-auto max-w-6xl px-4 py-6 sm:px-8"
        id="main-content"
      >
        <Link
          className="inline-flex min-h-11 items-center rounded text-sm font-semibold text-violet-800 hover:underline focus-visible:ring-2 focus-visible:ring-violet-700"
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
      className="workspace-shell profile-workspace mx-auto max-w-6xl px-4 py-6 sm:px-8"
      id="main-content"
    >
      <div aria-atomic="true" aria-live="polite" className="sr-only">
        {announcement}
      </div>
      <Link
        className="profile-breadcrumbs inline-flex min-h-11 items-center rounded text-sm font-medium text-[var(--muted)] hover:text-[var(--text)] focus-visible:ring-2 focus-visible:ring-[var(--accent)]"
        href="/roles"
      >
        ← Back to roles
      </Link>

      <header className="profile-page-header mt-4 border-b border-[var(--border)] pb-6">
        <div className="flex flex-col justify-between gap-5 xl:flex-row xl:items-center">
          <div className="min-w-0 break-words">
            <div className="flex flex-wrap items-center gap-3">
              <p className="text-xs font-medium text-[var(--muted)]">
                {state.role.department}
              </p>
              <StatusBadge status={state.role.status} />
            </div>
            <h1 className="workspace-title mt-3 break-words text-2xl font-semibold tracking-tight text-slate-900 sm:text-[28px]">
              {state.role.title}
            </h1>
            <p className="mt-2 text-sm text-[var(--muted)]">
              {state.role.location} · Created{" "}
              {formatDate(state.role.created_at)}
            </p>
          </div>
          <div className="profile-page-actions flex shrink-0 flex-wrap items-center gap-2">
            <Link
              href={`/roles/${roleId}/reports`}
              className="action-secondary"
            >
              View recruiter reports
            </Link>
            {canManageInvitations(state.user.role) ? (
              <Link
                className="action-primary"
                href={`/roles/${roleId}/invites`}
              >
                Manage invitations
              </Link>
            ) : null}
          </div>
        </div>
        <details className="profile-source mt-5 border-t border-[var(--border)] pt-2">
          <summary className="min-h-11 cursor-pointer content-center py-2 text-sm font-medium text-[var(--muted)] focus-visible:ring-2 focus-visible:ring-[var(--accent)]">
            Source job description
          </summary>
          <p className="mt-4 whitespace-pre-wrap break-words text-sm leading-7 text-slate-700">
            {state.role.job_description}
          </p>
        </details>
      </header>
      <RoleMaintenance
        key={state.role.id}
        role={state.role}
        userRole={state.user.role}
        descriptionLocked={state.profiles.length > 0}
        onChanged={(role) => {
          setState((current) =>
            current.status === "ready" && current.role.id === role.id
              ? { ...current, role }
              : current,
          );
          if (role.status === "archived") setStartingReplacement(false);
        }}
      />

      <div className="profile-context-layout mt-8 grid gap-8 lg:grid-cols-[12rem_minmax(0,1fr)]">
        <aside
          aria-labelledby="version-history-title"
          className="profile-version-nav"
        >
          <div className="lg:sticky lg:top-5">
            <h2
              className="text-xs font-medium text-[var(--muted)]"
              id="version-history-title"
            >
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
                      className={`profile-version-button w-full min-h-11 rounded-lg border px-3 py-3 text-left transition focus-visible:ring-2 focus-visible:ring-[var(--accent)] ${
                        profile.id === selectedProfile?.id
                          ? "border-[var(--border)] bg-[var(--canvas)]"
                          : "border-transparent hover:bg-[var(--canvas)]"
                      }`}
                      onClick={() => setSelectedProfileId(profile.id)}
                      type="button"
                    >
                      <span className="flex items-center justify-between gap-2">
                        <span className="text-sm font-semibold text-slate-900">
                          Version {profile.version}
                        </span>{" "}
                        <StatusBadge status={profile.status} />
                      </span>{" "}
                      <span className="mt-1 block text-xs text-slate-600">
                        {formatDate(profile.created_at)}
                      </span>
                    </button>
                  </li>
                ))}
              </ol>
            )}
            <div className="mt-5 border-t border-slate-200 pt-4 text-xs leading-5 text-slate-600">
              Editing a draft creates a new version. Historical ratings are
              never overwritten.
            </div>
          </div>
        </aside>

        <section
          aria-labelledby="profile-review-title"
          className="profile-reading-pane min-w-0"
        >
          <div className="mb-5 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
            <div>
              <p className="text-xs font-medium text-[var(--muted)]">
                Human review
              </p>
              <h2
                className="mt-1 text-xl font-medium tracking-tight text-[var(--text)]"
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

          {!selectedProfile &&
          canCreateProfiles(state.user.role) &&
          state.role.status !== "archived" ? (
            <div className="space-y-6">
              <section
                aria-labelledby="extraction-title"
                className="surface rounded-lg border border-slate-200 bg-white p-4 sm:p-5"
              >
                <h3
                  className="text-lg font-semibold text-violet-950"
                  id="extraction-title"
                >
                  Generate a structured draft
                </h3>
                <p className="mt-2 text-sm leading-6 text-violet-900">
                  Extract all six construct ratings from the stored job
                  description. The result remains a draft until a hiring manager
                  reviews and approves it.
                </p>
                <button
                  className="mt-4 action-primary min-h-11 rounded-md bg-[var(--accent,#6253c7)] px-5 py-2.5 text-sm font-semibold text-white hover:bg-violet-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-700 focus-visible:ring-offset-2 disabled:cursor-wait disabled:opacity-70"
                  disabled={extracting}
                  onClick={() => void handleExtraction()}
                  type="button"
                >
                  {extracting
                    ? "Extracting structured draft…"
                    : "Extract profile from job description"}
                </button>
                {extractionError ? (
                  <p
                    className="mt-3 text-sm font-semibold text-rose-900"
                    role="alert"
                  >
                    {extractionError}
                  </p>
                ) : null}
              </section>

              <details className="border-t border-slate-200 pt-3">
                <summary className="min-h-11 cursor-pointer content-center py-2 font-semibold text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-700">
                  Create a manual draft instead
                </summary>
                <div className="mt-5">
                  <ProfileEditor
                    initialConstructs={blankConstructs()}
                    mode="create"
                    onSaved={handleSaved}
                    role={state.role}
                  />
                </div>
              </details>
            </div>
          ) : null}

          {selectedProfile && selectedProfile.assumptions.length > 0 ? (
            <section
              aria-labelledby="assumptions-title"
              className="mb-5 border-l-2 border-amber-400 bg-amber-50 px-4 py-3"
            >
              <h3
                className="font-semibold text-amber-950"
                id="assumptions-title"
              >
                Extraction assumptions to verify
              </h3>
              <ul className="mt-2 list-disc space-y-1 pl-5 text-sm leading-6 text-amber-900">
                {selectedProfile.assumptions.map((assumption, index) => (
                  <li key={`${selectedProfile.id}-assumption-${index}`}>
                    {assumption}
                  </li>
                ))}
              </ul>
            </section>
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
              className="mt-5 action-secondary min-h-11 rounded-md border border-violet-700 bg-white px-5 py-2.5 text-sm font-semibold text-violet-800 hover:bg-violet-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-700 focus-visible:ring-offset-2"
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
              className="mt-6 border-t border-slate-200 pt-5"
              aria-labelledby="approval-title"
            >
              <h3
                className="text-lg font-semibold text-slate-900"
                id="approval-title"
              >
                Approval decision
              </h3>
              <p className="mt-2 text-sm leading-6 text-slate-700">
                Confirm that all six ratings and evidence excerpts reflect the
                role. Approval freezes this version for downstream use.
              </p>
              <button
                className="action-primary mt-4 min-h-11 rounded-md bg-[var(--accent,#6253c7)] px-5 py-2.5 text-sm font-semibold text-white hover:bg-violet-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-700 focus-visible:ring-offset-2"
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
            <p className="mt-5 rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
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
    <form
      className="profile-editor surface space-y-5 rounded-lg border border-[var(--border)] bg-white p-4 sm:p-6"
      onSubmit={handleSubmit}
    >
      <p className="border-l-2 border-violet-700 pl-4 text-sm leading-6 text-slate-700">
        Evidence must be copied verbatim from the source job description.
        Ratings describe role behavior on a 1–5 scale; they are not candidate
        scores.
      </p>
      {constructs.map((construct, index) => {
        const definition = CONSTRUCT_DEFINITIONS_BY_KEY[construct.key];
        const fieldPrefix = `${mode}-${construct.key}`;
        return (
          <fieldset
            className="min-w-0 border-t border-slate-200 py-5"
            disabled={saving}
            key={construct.key}
          >
            <legend className="px-1 text-lg font-semibold text-slate-950">
              <span className="mr-2 text-sm text-slate-600">{index + 1}/6</span>
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
                <span className="field-label block text-sm font-semibold text-slate-800">
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
                      <span className="grid min-h-11 place-items-center rounded-lg border border-slate-300 bg-white text-sm font-semibold text-slate-700 peer-checked:border-violet-700 peer-checked:bg-violet-50 peer-checked:text-violet-900 peer-focus-visible:ring-2 peer-focus-visible:ring-violet-700 peer-focus-visible:ring-offset-2">
                        {rating}
                      </span>
                    </label>
                  ))}
                </div>
                <span
                  className="mt-1 flex justify-between text-xs text-slate-600"
                  id={`${fieldPrefix}-scale-help`}
                >
                  <span>Low</span>
                  <span>High</span>
                </span>
              </div>
              <label className="field-label block text-sm font-semibold text-slate-800">
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

            <label className="mt-5 field-label block text-sm font-semibold text-slate-800">
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
            <label className="mt-5 field-label block text-sm font-semibold text-slate-800">
              Job-description evidence
              <span className="mt-1 block text-xs font-normal text-slate-600">
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
          className="rounded-md border border-rose-200 bg-rose-50 px-4 py-3 text-sm font-semibold text-rose-900"
          role="alert"
        >
          {saveError}
        </p>
      ) : null}
      <div className="flex flex-col gap-3 border-t border-slate-200 pt-4 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm text-slate-600">
          {mode === "create"
            ? `Creates draft version ${nextVersion ?? 1}.`
            : `Saves as version ${(profile?.version ?? 0) + 1}; version ${profile?.version} remains unchanged.`}
        </p>
        <button
          className="action-primary min-h-11 shrink-0 rounded-md bg-[var(--accent,#6253c7)] px-5 py-2.5 text-sm font-semibold text-white hover:bg-violet-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-700 focus-visible:ring-offset-2"
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
    <div className="profile-constructs space-y-2">
      {profile.status === "approved" ? (
        <p className="profile-frozen-note mb-5 border-l-2 border-[var(--accent)] bg-[var(--canvas)] px-4 py-3 text-sm leading-6 text-[var(--muted)]">
          Approved versions are frozen. Create a new complete draft to propose
          future changes.
        </p>
      ) : null}
      {profile.constructs.map((construct, index) => {
        const definition = CONSTRUCT_DEFINITIONS_BY_KEY[construct.key];
        return (
          <article
            aria-labelledby={`construct-${profile.id}-${construct.key}`}
            className="profile-construct min-w-0 border-t border-[var(--border)] py-6"
            key={construct.key}
          >
            <div className="profile-construct-heading flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
              <div>
                <p className="text-xs font-medium text-[var(--muted)]">
                  Construct {index + 1} of 6
                </p>
                <h3
                  className="mt-1 text-lg font-medium text-[var(--text)]"
                  id={`construct-${profile.id}-${construct.key}`}
                >
                  {definition.label}
                </h3>
                <p className="mt-1 text-sm leading-6 text-slate-600">
                  {definition.role_prompt}
                </p>
              </div>
              <div className="profile-construct-rating flex shrink-0 flex-col gap-1.5 sm:items-end">
                <span className="text-sm font-medium text-[var(--text)]">
                  Rating {construct.rating}/5
                </span>
                <span
                  className="profile-rating-indicator flex gap-1"
                  aria-hidden="true"
                >
                  {[1, 2, 3, 4, 5].map((value) => (
                    <span
                      key={value}
                      className={`h-1 w-4 rounded-sm ${value <= construct.rating ? "bg-[var(--accent)]" : "bg-[var(--border)]"}`}
                    />
                  ))}
                </span>
                <span className="text-xs capitalize text-[var(--muted)]">
                  {construct.confidence} confidence
                </span>
              </div>
            </div>
            <div className="profile-evidence-grid mt-5 grid gap-5 xl:grid-cols-2">
              <div>
                <h4 className="text-xs font-medium text-[var(--muted)]">
                  Review rationale
                </h4>
                <p className="mt-2 text-sm leading-6 text-slate-700">
                  {construct.rationale}
                </p>
              </div>
              <div>
                <h4 className="text-xs font-medium text-[var(--muted)]">
                  Source evidence
                </h4>
                <ul className="mt-2 space-y-2">
                  {construct.evidence.map((excerpt, excerptIndex) => (
                    <li
                      className="border-l-2 border-[var(--border)] pl-3 text-sm leading-6 text-[var(--muted)]"
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
