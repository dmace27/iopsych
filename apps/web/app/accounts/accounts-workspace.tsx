"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { ApiClientError, getCurrentUser } from "../../lib/api-client";
import { getAccounts, updateAccount } from "../../lib/account-client";
import type {
  Account,
  AccountPage,
  AccountUpdate,
} from "../../lib/account-contracts";
import type { CurrentUser } from "../../lib/contracts";
import { signInHref } from "../../lib/safe-return-to";

const button =
  "action-secondary min-h-11 rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-semibold disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-700";
const roles = ["admin", "recruiter", "hiring_manager"] as const;
const roleName = (role: string) => role.replaceAll("_", " ");
type Pending = { account: Account; update: AccountUpdate };

export function AccountsWorkspace() {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [page, setPage] = useState<AccountPage | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [notice, setNotice] = useState("");
  const [pending, setPending] = useState<Pending | null>(null);
  const [needsRefresh, setNeedsRefresh] = useState(false);
  const [cursor, setCursor] = useState<string | undefined>();
  const [history, setHistory] = useState<(string | undefined)[]>([]);
  const busy = useRef(false);
  const generation = useRef(0);
  const feedback = useRef<HTMLDivElement>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const cancel = useRef<HTMLButtonElement>(null);
  const trigger = useRef<HTMLButtonElement | null>(null);

  async function load(after?: string, previous: (string | undefined)[] = []) {
    if (busy.current) return;
    busy.current = true;
    const request = ++generation.current;
    setLoading(true);
    setNotice("");
    setPending(null);
    setError(null);
    setPage(null);
    try {
      const current = await getCurrentUser();
      if (request !== generation.current) return;
      setUser(current);
      if (current.role !== "admin") return;
      const result = await getAccounts({ after });
      if (request !== generation.current) return;
      setPage(result);
      setCursor(after);
      setHistory(previous);
      setNeedsRefresh(false);
    } catch (cause) {
      if (request !== generation.current) return;
      setError(
        cause instanceof Error
          ? cause
          : new Error("Accounts could not be loaded."),
      );
    } finally {
      if (request === generation.current) {
        busy.current = false;
        setLoading(false);
      }
    }
  }

  function invalidateRequests() {
    ++generation.current;
    busy.current = false;
  }
  useEffect(() => {
    let active = true;
    void Promise.resolve().then(() => {
      if (active) void load();
    });
    return () => {
      active = false;
      invalidateRequests();
    };
  }, []);
  useEffect(() => {
    if (pending) cancel.current?.focus();
    else if (!error && !notice) trigger.current?.focus();
  }, [pending, error, notice]);
  useEffect(() => {
    if (!loading && (error || notice)) feedback.current?.focus();
  }, [error, notice, loading]);

  function review(
    account: Account,
    update: AccountUpdate,
    source: HTMLButtonElement,
  ) {
    trigger.current = source;
    setNotice("");
    setPending({ account, update });
  }
  function dismiss() {
    setPending(null);
  }
  async function confirm() {
    if (!pending || busy.current) return;
    busy.current = true;
    setSaving(true);
    setError(null);
    try {
      const updated = await updateAccount(pending.account.id, pending.update);
      setPage((current) =>
        current
          ? {
              ...current,
              items: current.items.map((item) =>
                item.id === updated.id ? updated : item,
              ),
            }
          : current,
      );
      setNotice(`Access updated for ${updated.name}.`);
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause
          : new Error("The change could not be confirmed. Refresh accounts."),
      );
      setNeedsRefresh(true);
    } finally {
      setPending(null);
      busy.current = false;
      setSaving(false);
    }
  }

  useEffect(() => {
    if (!loading && !error) heading.current?.focus();
  }, [loading, error]);

  const expired = error instanceof ApiClientError && error.status === 401;
  const denied = error instanceof ApiClientError && error.status === 403;
  return (
    <main
      id="main-content"
      className="workspace-shell mx-auto max-w-6xl space-y-5 px-5 py-8 text-slate-900 sm:px-8"
    >
      <h1
        ref={heading}
        tabIndex={-1}
        className="workspace-title text-2xl font-semibold text-slate-950"
      >
        Accounts
      </h1>
      <p className="text-slate-600">
        Manage existing accounts in your organization. Each account belongs to
        one organization; organization switching is unavailable.
      </p>
      <div
        ref={feedback}
        tabIndex={-1}
        className="rounded-md focus-visible:outline-2 focus-visible:outline-teal-700"
      >
        {error ? <p role="alert">{error.message}</p> : null}
        {notice ? <p role="status">{notice}</p> : null}
        {expired ? (
          <Link className="underline" href={signInHref("/accounts")}>
            Sign in to continue
          </Link>
        ) : null}
      </div>
      {loading ? <p role="status">Loading accounts…</p> : null}
      {!loading && user && user.role !== "admin" ? (
        <p role="alert">Only administrators can manage accounts.</p>
      ) : null}
      {!loading && !expired && !denied && (!user || user.role === "admin") ? (
        <button
          className={button}
          disabled={saving || !!pending}
          onClick={() => {
            setNotice("");
            void load();
          }}
        >
          Refresh accounts
        </button>
      ) : null}
      {page && !expired && !denied ? (
        <>
          <p className="text-sm text-slate-600">
            Up to 25 accounts per page. Your own account is read-only.
          </p>
          {page.items.length === 0 ? <p>No accounts on this page.</p> : null}
          <ul
            className="record-list surface divide-y divide-slate-200 border-y border-slate-200 bg-white"
            aria-label="Organization accounts"
          >
            {page.items.map((account) => (
              <AccountRow
                key={`${account.id}:${account.version}`}
                account={account}
                self={account.id === user?.id}
                disabled={saving || !!pending || needsRefresh}
                onReview={review}
              />
            ))}
          </ul>
          <nav aria-label="Account pages" className="flex flex-wrap gap-3">
            <button
              className={button}
              disabled={!history.length || saving || !!pending || needsRefresh}
              onClick={() => void load(history.at(-1), history.slice(0, -1))}
            >
              Previous page
            </button>
            <button
              className={button}
              disabled={
                !page.next_cursor || saving || !!pending || needsRefresh
              }
              onClick={() =>
                void load(page.next_cursor ?? undefined, [...history, cursor])
              }
            >
              Next page
            </button>
          </nav>
        </>
      ) : null}
      {pending ? (
        <section
          role="alertdialog"
          aria-labelledby="account-confirm-title"
          aria-describedby="account-confirm-detail"
          className="surface space-y-3 border-l-4 border-teal-700 bg-white p-4 [overflow-wrap:anywhere]"
          onKeyDown={(event) => {
            if (event.key === "Escape" && !saving) dismiss();
          }}
        >
          <h2 id="account-confirm-title" className="text-lg font-semibold">
            Confirm access change
          </h2>
          <p id="account-confirm-detail">
            {pending.account.name} ({pending.account.email}):{" "}
            {pending.update.role
              ? `change role from ${roleName(pending.account.role)} to ${roleName(pending.update.role)}`
              : pending.update.is_active
                ? "reactivate access"
                : "deactivate access"}
            . This changes their access on subsequent requests.
          </p>
          <div className="mt-4 flex flex-wrap gap-3">
            <button
              ref={cancel}
              className={button}
              disabled={saving}
              onClick={dismiss}
            >
              Cancel
            </button>
            <button
              className="action-primary min-h-11 rounded-md bg-teal-700 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-700"
              disabled={saving}
              onClick={() => void confirm()}
            >
              {saving ? "Saving…" : "Confirm change"}
            </button>
          </div>
        </section>
      ) : null}
    </main>
  );
}

function AccountRow({
  account,
  self,
  disabled,
  onReview,
}: {
  account: Account;
  self: boolean;
  disabled: boolean;
  onReview: (
    account: Account,
    update: AccountUpdate,
    source: HTMLButtonElement,
  ) => void;
}) {
  const [role, setRole] = useState(account.role);
  return (
    <li className="record-row grid gap-3 px-4 py-4 lg:grid-cols-[minmax(12rem,1fr)_minmax(0,2fr)] lg:gap-x-6">
      <div className="min-w-0 space-y-1">
        <h2 className="font-semibold [overflow-wrap:anywhere]">
          {account.name}
          {self ? " (you)" : ""}
        </h2>
        <p className="break-all text-sm">{account.email}</p>
        <p className="text-sm text-slate-600">
          {roleName(account.role)} · {account.is_active ? "Active" : "Inactive"}
        </p>
      </div>
      {self ? (
        <p className="text-sm">
          Your account is read-only. Another administrator must change your
          access.
        </p>
      ) : (
        <div className="flex min-w-0 flex-wrap items-end gap-3">
          <div className="w-full sm:w-auto">
            <label
              className="field-label mb-1 block text-sm font-medium [overflow-wrap:anywhere]"
              htmlFor={`role-${account.id}`}
            >
              Role for {account.name}
            </label>
            <select
              id={`role-${account.id}`}
              className="min-h-11 w-full rounded-md border border-slate-300 bg-white p-2 text-sm focus-visible:outline-2 focus-visible:outline-teal-700"
              value={role}
              disabled={disabled}
              onChange={(event) =>
                setRole(event.target.value as Account["role"])
              }
            >
              {roles.map((value) => (
                <option key={value} value={value}>
                  {roleName(value)}
                </option>
              ))}
            </select>
          </div>
          <button
            className={button}
            disabled={disabled || role === account.role}
            onClick={(event) =>
              onReview(
                account,
                { expected_version: account.version, role },
                event.currentTarget,
              )
            }
          >
            Review role change
          </button>
          <button
            className={button}
            disabled={disabled}
            onClick={(event) =>
              onReview(
                account,
                {
                  expected_version: account.version,
                  is_active: !account.is_active,
                },
                event.currentTarget,
              )
            }
          >
            {account.is_active ? "Deactivate" : "Reactivate"}
          </button>
        </div>
      )}
    </li>
  );
}
