import type { Metadata } from "next";
import { ReportWorkspace } from "../report-workspace";
export const metadata: Metadata = { title: "Recruiter report" };
export default async function ReportPage({
  params,
}: {
  params: Promise<{ reportId: string }>;
}) {
  const { reportId } = await params;
  return <ReportWorkspace reportId={reportId} />;
}
