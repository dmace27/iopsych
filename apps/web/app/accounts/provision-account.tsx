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
    <form onSubmit={create} className="space-y-3 rounded-xl border p-5">
      <h2 className="text-xl font-bold">Provision account</h2>
      <p>
        Create the account in Auth0 first, then copy its exact User ID. Email
        never grants access automatically.
      </p>
      {error ? <p role="alert">{error}</p> : null}
      <fieldset disabled={disabled || saving} className="space-y-3">
        <label className="block">
          Auth0 User ID
          <input
            className="field-control"
            required
            name="subject"
            maxLength={255}
          />
        </label>
        <label className="block">
          Name
          <input
            className="field-control"
            required
            name="name"
            maxLength={160}
          />
        </label>
        <label className="block">
          Email
          <input
            className="field-control"
            required
            name="email"
            type="email"
            maxLength={320}
          />
        </label>
        <label className="block">
          Permission
          <select name="role" className="field-control">
            <option value="recruiter">Recruiter</option>
            <option value="hiring_manager">Hiring manager</option>
            <option value="admin">Administrator</option>
          </select>
        </label>
        <button type="submit" className="rounded-md border px-3 py-2">
          {saving ? "Provisioning…" : "Provision account"}
        </button>
      </fieldset>
    </form>
  );
}
