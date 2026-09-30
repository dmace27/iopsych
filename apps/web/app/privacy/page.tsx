import type { Metadata } from "next";

import { PrivacyWorkspace } from "./privacy-workspace";

export const metadata: Metadata = {
  title: "Privacy administration",
};

/** Render the administrator-only candidate privacy workspace. */
export default function PrivacyPage() {
  return <PrivacyWorkspace />;
}
