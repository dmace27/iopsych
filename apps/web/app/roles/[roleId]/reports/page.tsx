import type { Metadata } from "next";
import { RecruiterReportsWorkspace } from "../../../reports/report-workspace";
export const metadata: Metadata = { title: "Recruiter reports" };
export default async function ReportsPage({
  params,
}: {
  params: Promise<{ roleId: string }>;
}) {
  const { roleId } = await params;
  return <RecruiterReportsWorkspace roleId={roleId} />;
}
