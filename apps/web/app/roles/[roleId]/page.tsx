import type { Metadata } from "next";

import { RoleProfileWorkspace } from "./role-profile-workspace";

export const metadata: Metadata = {
  title: "Role profile",
};

/** Render one role and its immutable profile history. */
export default async function RoleProfilePage({
  params,
}: {
  params: Promise<{ roleId: string }>;
}) {
  const { roleId } = await params;
  return <RoleProfileWorkspace roleId={roleId} />;
}
