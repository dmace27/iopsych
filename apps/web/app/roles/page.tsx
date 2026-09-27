import type { Metadata } from "next";

import { RolesWorkspace } from "./roles-workspace";

export const metadata: Metadata = {
  title: "Roles",
};

/** Render the internal organization role workspace. */
export default function RolesPage() {
  return <RolesWorkspace />;
}
