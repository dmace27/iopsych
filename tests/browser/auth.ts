import { expect, type Page } from "@playwright/test";

/** Exercise the real cookie exchange without depending on a token-paste UI. */
export async function exchangeSession(page: Page, token: string) {
  if (new URL(page.url()).origin !== "http://127.0.0.1:3116")
    throw new Error("Synthetic sign-in requires the owned browser origin");
  return page.evaluate(async (token) => {
    const response = await fetch("/api/session", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token }),
    });
    return response.status;
  }, token);
}

export async function syntheticSignIn(page: Page, identity = "RECRUITER") {
  const token = process.env[`BROWSER_E2E_${identity}`];
  if (!token) throw new Error("Missing isolated synthetic identity");
  await page.goto("/sign-in");
  expect(await exchangeSession(page, token)).toBe(200);
  await page.goto("/roles");
}
