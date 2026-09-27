import type { Metadata } from "next";

import { CandidateAssessment } from "./candidate-assessment";

export const metadata: Metadata = {
  description:
    "Review consent information and complete a work-preference assessment.",
  title: "Candidate assessment",
};

export default async function CandidateInvitePage({
  params,
}: PageProps<"/candidate/invites/[token]">) {
  const { token } = await params;
  return <CandidateAssessment token={token} />;
}
