import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getCandidateInvite, recordCandidateConsent } from "./candidate-api";

const response = {
  can_start_assessment: false,
  consent_notice: {
    accommodation_contact_email: "access@example.invalid",
    data_use: "Interview preparation.",
    decline_without_penalty: true,
    privacy_contact_email: "privacy@example.invalid",
    purpose: "Work preferences.",
    retention: "90 days.",
    version: "pilot-1",
  },
  decision: null,
  decision_recorded_at: null,
  expires_at: "2026-10-01T12:00:00Z",
  invitation_id: "11111111-1111-4111-8111-111111111111",
  organization_name: "Northstar Labs",
  role_title: "Platform Engineer",
  status: "active",
};

describe("candidate API client", () => {
  beforeEach(() => vi.stubGlobal("fetch", vi.fn()));
  afterEach(() => vi.unstubAllGlobals());

  it("loads and validates a candidate-safe invite", async () => {
    vi.mocked(fetch).mockResolvedValue(Response.json(response));

    await expect(getCandidateInvite("signed/token")).resolves.toEqual(response);
    expect(fetch).toHaveBeenCalledWith(
      "/api/candidate/invites/signed%2Ftoken",
      expect.objectContaining({ cache: "no-store" }),
    );
  });

  it("posts the exact terminal consent contract", async () => {
    vi.mocked(fetch).mockResolvedValue(
      Response.json({
        ...response,
        can_start_assessment: true,
        decision: "consent",
        status: "consented",
      }),
    );

    await recordCandidateConsent("token", "consent");

    expect(fetch).toHaveBeenCalledWith(
      "/api/candidate/invites/token/consent",
      expect.objectContaining({
        body: JSON.stringify({ decision: "consent" }),
        method: "POST",
      }),
    );
  });

  it("normalizes problem responses and invalid successful payloads", async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(
        Response.json(
          {
            code: "invitation_expired",
            detail: "This invitation has expired.",
            status: 410,
            title: "Unavailable",
            type: "about:blank",
          },
          { status: 410 },
        ),
      )
      .mockResolvedValueOnce(Response.json({ unexpected: true }));

    await expect(getCandidateInvite("expired")).rejects.toMatchObject({
      code: "invitation_expired",
      message: "This invitation has expired.",
      status: 410,
    });
    await expect(getCandidateInvite("invalid")).rejects.toMatchObject({
      code: "invalid_api_response",
    });
  });

  it("does not expose fetch failures or non-problem response bodies", async () => {
    vi.mocked(fetch)
      .mockRejectedValueOnce(new Error("private network detail"))
      .mockResolvedValueOnce(new Response("not json", { status: 500 }));

    await expect(getCandidateInvite("token")).rejects.toEqual(
      expect.objectContaining({
        code: "network_error",
        message: "The assessment service could not be reached.",
      }),
    );
    await expect(getCandidateInvite("token")).rejects.toMatchObject({
      code: "unexpected_response",
      message: "This invitation could not be opened.",
    });
  });
});
