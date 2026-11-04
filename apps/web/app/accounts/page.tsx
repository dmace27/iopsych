import type { Metadata } from "next";
import { AccountsWorkspace } from "./accounts-workspace";

export const metadata: Metadata = { title: "Accounts" };
export default function AccountsPage() {
  return <AccountsWorkspace />;
}
