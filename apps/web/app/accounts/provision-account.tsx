"use client";

import { useRef, useState } from "react";
import { provisionUser } from "../../lib/api-client";
import type { InternalUserRole } from "../../lib/contracts";

/** Provision an existing provider identity; access edits remain version checked. */
export function ProvisionAccount({
  disabled,
  onCreated,
}: {
  disabled: boolean;
  onCreated: () => void;
}) {
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const busy = useRef(false);
  async function create(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy.current || disabled) return;
    busy.current = true;
    const form = event.currentTarget;
    const data = new FormData(form);
    setSaving(true);
    setError(null);
    try {
      await provisionUser({
        auth_subject: String(data.get("subject")),
        email: String(data.get("email")),
        name: String(data.get("name")),
        role: data.get("role") as InternalUserRole,
      });
      form.reset();
      onCreated();
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Account could not be provisioned.",
      );
    } finally {
      busy.current = false;
      setSaving(false);
    }
  }
  return (
    <form
      onSubmit={create}
      className="admin-section admin-provision grid gap-6 border-y border-[var(--border)] py-6 lg:grid-cols-[minmax(12rem,1fr)_minmax(0,2fr)]"
    >
      <div>
        <h2 className="text-base font-semibold">Provision account</h2>
        <p className="mt-2 max-w-sm text-sm leading-6 text-[var(--muted)]">
          Create the account in Auth0 first, then copy its exact User ID. Email
          never grants access automatically.
        </p>
        {error ? <p role="alert">{error}</p> : null}
      </div>
      <fieldset
        disabled={disabled || saving}
        className="grid min-w-0 gap-4 sm:grid-cols-2"
      >
        <label className="field-label block sm:col-span-2">
          Auth0 User ID
          <input
            className="field-control mt-2"
            required
            name="subject"
            maxLength={255}
          />
        </label>
        <label className="field-label block">
          Name
          <input
            className="field-control mt-2"
            required
            name="name"
            maxLength={160}
          />
        </label>
        <label className="field-label block">
          Email
          <input
            className="field-control mt-2"
            required
            name="email"
            type="email"
            maxLength={320}
          />
        </label>
        <label className="field-label block sm:col-span-2">
          Permission
          <select name="role" className="field-control mt-2">
            <option value="recruiter">Recruiter</option>
            <option value="hiring_manager">Hiring manager</option>
            <option value="admin">Administrator</option>
          </select>
        </label>
        <button
          type="submit"
          className="action-primary justify-self-start sm:col-span-2"
        >
          {saving ? "Provisioning…" : "Provision account"}
        </button>
      </fieldset>
    </form>
  );
}
