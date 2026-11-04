"use client";

import { useRef, useState } from "react";
import type { InternalUserRole, Role } from "../../../lib/contracts";
import { archiveRole, updateRole } from "../../../lib/role-maintenance-client";
import {
  canMaintainRole,
  RoleUpdateSchema,
  type RoleUpdateInput,
} from "../../../lib/role-maintenance-contracts";

const fields = [
  ["title", "Role title", 160],
  ["department", "Department", 160],
  ["location", "Location", 160],
  ["job_description", "Job description", 100_000],
] as const;
const buttonClass =
  "min-h-11 rounded-lg border border-slate-400 px-4 py-2 font-bold focus-visible:ring-2 focus-visible:ring-teal-700 disabled:opacity-50";

export function RoleMaintenance({
  role,
  userRole,
  onChanged,
  descriptionLocked = false,
}: {
  role: Role;
  userRole: InternalUserRole;
  onChanged: (role: Role) => void;
  descriptionLocked?: boolean;
}) {
  const [confirming, setConfirming] = useState(false);
  const [editing, setEditing] = useState(false);
  const [values, setValues] = useState(() => ({
    title: role.title,
    department: role.department,
    location: role.location,
    job_description: role.job_description,
  }));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const dialog = useRef<HTMLDialogElement>(null);
  const cancel = useRef<HTMLButtonElement>(null);
  const archiveButton = useRef<HTMLButtonElement>(null);
  const editButton = useRef<HTMLButtonElement>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const inFlight = useRef(false);
  const writable = canMaintainRole(userRole) && role.status !== "archived";

  function closeDialog() {
    setConfirming(false);
    dialog.current?.close();
    archiveButton.current?.focus();
  }
  async function save(event: React.FormEvent) {
    event.preventDefault();
    if (!writable || inFlight.current) return;
    const patch: RoleUpdateInput = {};
    for (const [key] of fields)
      if (
        !(descriptionLocked && key === "job_description") &&
        values[key].trim() !== role[key]
      )
        patch[key] = values[key];
    const parsed = RoleUpdateSchema.safeParse(patch);
    if (!parsed.success) {
      setError(
        parsed.error.issues
          .map((issue) => `${issue.path.join(" ")}: ${issue.message}`)
          .join(" "),
      );
      return;
    }
    inFlight.current = true;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const saved = await updateRole(role.id, parsed.data);
      onChanged(saved);
      setEditing(false);
      setNotice("Role details saved. Existing profile versions are unchanged.");
      heading.current?.focus();
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Role details could not be saved.",
      );
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  }
  async function archive() {
    if (!writable || inFlight.current) return;
    inFlight.current = true;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await archiveRole(role.id);
      closeDialog();
      onChanged({ ...role, status: "archived" });
      setEditing(false);
      setNotice("Role archived. History is preserved.");
      heading.current?.focus();
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "The role could not be archived.",
      );
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  }
  return (
    <section
      aria-labelledby="role-maintenance-title"
      className="mt-6 space-y-4 rounded-2xl border border-slate-200 bg-white p-6"
    >
      <h2
        id="role-maintenance-title"
        ref={heading}
        tabIndex={-1}
        className="text-xl font-bold"
      >
        Role maintenance
      </h2>
      <p>
        Archiving preserves profile and audit history and blocks new writes. It
        does not delete candidate data.
      </p>
      <p role="status">{notice}</p>
      {role.status === "archived" ? (
        <p>This archived role is read-only.</p>
      ) : !writable ? (
        <p>
          Only administrators and recruiters can edit details or archive this
          role.
        </p>
      ) : (
        <>
          <div className="flex gap-3">
            <button
              ref={editButton}
              className={buttonClass}
              disabled={busy || editing}
              onClick={() => {
                setValues({
                  title: role.title,
                  department: role.department,
                  location: role.location,
                  job_description: role.job_description,
                });
                setError("");
                setEditing(true);
              }}
            >
              Edit role details
            </button>
            <button
              ref={archiveButton}
              className={buttonClass}
              disabled={busy || editing}
              onClick={() => {
                setError("");
                setConfirming(true);
                dialog.current?.showModal();
                cancel.current?.focus();
              }}
            >
              Archive role
            </button>
          </div>
          {editing ? (
            <form onSubmit={save} className="space-y-4">
              <p>
                Changes update role metadata only. Existing profile versions and
                approvals remain unchanged.
              </p>
              <fieldset disabled={busy} className="space-y-4">
                <legend className="sr-only">Role details</legend>
                {fields.map(([key, label, limit]) => (
                  <label key={key} className="block font-bold">
                    {label}
                    <span className="block text-sm font-normal">
                      Required; up to {limit.toLocaleString()} characters.
                    </span>
                    {key === "job_description" ? (
                      <textarea
                        className="field-control"
                        disabled={descriptionLocked}
                        required
                        maxLength={limit}
                        value={values[key]}
                        onChange={(event) =>
                          setValues({ ...values, [key]: event.target.value })
                        }
                      />
                    ) : (
                      <input
                        className="field-control"
                        required
                        maxLength={limit}
                        value={values[key]}
                        onChange={(event) =>
                          setValues({ ...values, [key]: event.target.value })
                        }
                      />
                    )}
                  </label>
                ))}
                {descriptionLocked ? (
                  <p>
                    Job description is locked after profile versioning begins.
                  </p>
                ) : null}
                <button className={buttonClass} type="submit">
                  {busy ? "Saving role details…" : "Save role details"}
                </button>
                <button
                  className={buttonClass}
                  type="button"
                  onClick={() => {
                    setEditing(false);
                    setError("");
                    heading.current?.focus();
                  }}
                >
                  Cancel editing
                </button>
              </fieldset>
            </form>
          ) : null}
          <dialog
            ref={dialog}
            aria-labelledby="archive-role-title"
            aria-describedby="archive-role-description"
            className="m-auto max-w-lg space-y-4 rounded-2xl p-6 backdrop:bg-black/40"
            onCancel={(event) => {
              if (inFlight.current) event.preventDefault();
              else setConfirming(false);
            }}
            onClose={() => {
              if (!inFlight.current) archiveButton.current?.focus();
            }}
          >
            <h3 id="archive-role-title" className="text-xl font-bold">
              Archive {role.title}?
            </h3>
            <p id="archive-role-description">
              This blocks new writes for this role and preserves profile and
              audit history. This is not data deletion. There is no restore
              action in this workspace.
            </p>
            {error ? <p role="alert">{error}</p> : null}
            <button
              ref={cancel}
              className={buttonClass}
              disabled={busy}
              onClick={closeDialog}
            >
              Keep role
            </button>
            <button
              className={buttonClass}
              disabled={busy}
              onClick={() => void archive()}
            >
              {busy ? "Archiving role…" : "Confirm archive"}
            </button>
          </dialog>
        </>
      )}
      {error && !confirming ? <p role="alert">{error}</p> : null}
    </section>
  );
}
