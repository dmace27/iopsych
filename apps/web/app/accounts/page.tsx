import { AccountsWorkspace } from "./accounts-workspace";

/** Compose the administrator-only account workspace. */
export default function AccountsPage() {
  return (
    <main className="mx-auto max-w-5xl px-5 py-12" id="main-content">
      <h1 className="text-3xl font-bold">Organization accounts</h1>
      <AccountsWorkspace />
    </main>
  );
}
