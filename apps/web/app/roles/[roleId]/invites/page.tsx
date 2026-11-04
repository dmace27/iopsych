import type { Metadata } from "next";
import { InvitationWorkspace } from "./invitation-workspace";
export const metadata: Metadata = { title: "Invitations" };
export default async function InvitationsPage({
  params,
}: {
  params: Promise<{ roleId: string }>;
}) {
  const { roleId } = await params;
  return <InvitationWorkspace roleId={roleId} />;
}
