"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  ApiClientError,
  getCurrentUser,
  getManagedUsers,
  provisionUser,
  updateManagedUser,
} from "../../lib/api-client";
import type {
  CurrentUser,
  ManagedUser,
  InternalUserRole,
} from "../../lib/contracts";

const roles: InternalUserRole[] = ["recruiter", "hiring_manager", "admin"];

/** Provision provider subjects and change access without direct database edits. */
export function AccountsWorkspace() {
  const [actor, setActor] = useState<CurrentUser | null>(null);
  const [users, setUsers] = useState<ManagedUser[]>([]);
  const [offset, setOffset] = useState(0);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expired, setExpired] = useState(false);

  function failed(reason: unknown) {
    if (reason instanceof ApiClientError && reason.status === 401) {
      setActor(null);
      setUsers([]);
    }
    setExpired(reason instanceof ApiClientError && reason.status === 401);
    setError(
      reason instanceof Error
        ? reason.message
        : "Accounts could not be loaded. Try again.",
    );
  }

  useEffect(() => {
    let active = true;
    Promise.all([getCurrentUser(), getManagedUsers(offset)])
      .then(([current, accounts]) => {
        if (active) {
          setActor(current);
          setUsers(accounts);
          setError(null);
        }
      })
      .catch((reason) => {
        if (active) failed(reason);
      })
      .finally(() => {
        if (active) setBusy(false);
      });
    return () => {
      active = false;
    };
  }, [offset]);

  async function create(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    setBusy(true);
    setError(null);
    try {
      await provisionUser({
        auth_subject: String(data.get("subject")),
        email: String(data.get("email")),
        name: String(data.get("name")),
        role: data.get("role") as InternalUserRole,
      });
      setUsers(await getManagedUsers(offset));
      form.reset();
    } catch (reason) {
      failed(reason);
    } finally {
      setBusy(false);
    }
  }

  async function update(
    event: React.FormEvent<HTMLFormElement>,
    user: ManagedUser,
  ) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setBusy(true);
    setError(null);
    try {
      const updated = await updateManagedUser(
        user.id,
        data.get("role") as InternalUserRole,
        data.get("active") === "on",
      );
      setUsers((values) =>
        values.map((value) => (value.id === updated.id ? updated : value)),
      );
    } catch (reason) {
      failed(reason);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mt-6 space-y-6" aria-busy={busy}>
      <p>
        Each provider account belongs to one organization. Create the user in
        Auth0 first, then copy its exact User ID here. Email never grants access
        automatically. Disabling access takes effect on the next API request.
      </p>
      {error ? (
        <p role="alert">
          {error}{" "}
          {expired ? (
            <Link href="/sign-in?returnTo=%2Faccounts">Sign in again</Link>
          ) : null}
        </p>
      ) : null}
      {actor?.role === "admin" ? (
        <>
          <form onSubmit={create} className="space-y-3 rounded-xl border p-5">
            <h2 className="text-xl font-bold">Provision account</h2>
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
                {roles.map((role) => (
                  <option key={role} value={role}>
                    {role.replaceAll("_", " ")}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="submit"
              disabled={busy}
              className="rounded bg-teal-800 p-3 text-white"
            >
              Provision account
            </button>
          </form>
          <ul className="space-y-4">
            {users.map((user) => (
              <li key={user.id} className="rounded-xl border p-4">
                <p className="font-bold">
                  {user.name} · {user.email}
                </p>
                <p className="text-sm">
                  {user.auth_subject} · {user.is_active ? "Active" : "Disabled"}
                </p>
                <form
                  onSubmit={(event) => update(event, user)}
                  className="flex flex-wrap items-center gap-4 mt-3"
                >
                  <label>
                    Permission for {user.name}
                    <select
                      name="role"
                      defaultValue={user.role}
                      disabled={busy || user.id === actor.id}
                      className="field-control"
                    >
                      {roles.map((role) => (
                        <option key={role} value={role}>
                          {role.replaceAll("_", " ")}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    <input
                      name="active"
                      type="checkbox"
                      defaultChecked={user.is_active}
                      disabled={busy || user.id === actor.id}
                    />{" "}
                    Active access for {user.name}
                  </label>
                  <button type="submit" disabled={busy || user.id === actor.id}>
                    Save access for {user.name}
                  </button>
                </form>
              </li>
            ))}
          </ul>
          <div className="flex gap-5">
            <button
              disabled={busy || offset === 0}
              onClick={() => {
                setBusy(true);
                setOffset((value) => value - 50);
              }}
            >
              Previous accounts
            </button>
            <button
              disabled={busy || users.length < 50}
              onClick={() => {
                setBusy(true);
                setOffset((value) => value + 50);
              }}
            >
              Next accounts
            </button>
          </div>
        </>
      ) : !busy && !error ? (
        <p>Administrator access is required to manage accounts.</p>
      ) : null}
    </div>
  );
}
