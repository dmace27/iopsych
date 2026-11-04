/** @vitest-environment jsdom */
import { afterEach, expect, it, vi } from "vitest";
import { ApiClientError, getCurrentUser } from "./api-client";
afterEach(() => vi.unstubAllGlobals());
it("announces session expiry so navigation offers immediate recovery", async () => {
  const expired = vi.fn();
  window.addEventListener("iopsych:session-expired", expired);
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      Response.json(
        {
          type: "about:blank",
          title: "Authentication required",
          status: 401,
          code: "authentication_required",
        },
        { status: 401 },
      ),
    ),
  );
  try {
    await expect(getCurrentUser()).rejects.toBeInstanceOf(ApiClientError);
    expect(expired).toHaveBeenCalledOnce();
  } finally {
    window.removeEventListener("iopsych:session-expired", expired);
  }
});
