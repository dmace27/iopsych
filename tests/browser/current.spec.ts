import { exchangeSession, syntheticSignIn } from "./auth";
import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const role = "00000000-0000-4000-8000-000000000021";
const invitations = `/roles/${role}/invites`;

test.beforeEach(async ({ context }) => {
  await context.route("**/*", async (route) => {
    if (new URL(route.request().url()).origin !== "http://127.0.0.1:3116")
      throw new Error("Current browser matrix attempted an unowned request");
    await route.continue();
  });
});

async function signIn(page: Page, identity = "RECRUITER") {
  await syntheticSignIn(page, identity);
  await expect(
    page.getByRole("heading", { name: "Organization roles" }),
  ).toBeVisible();
}

async function inspect(page: Page) {
  const result = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
    .analyze();
  const summarize = (items: typeof result.violations) =>
    items.map((item) => ({ id: item.id, nodes: item.nodes.length }));
  console.log(
    "CURRENT_AXE " +
      JSON.stringify({
        test: test.info().title,
        width: page.viewportSize()?.width,
        violations: summarize(result.violations),
        incomplete: summarize(result.incomplete),
      }),
  );
  expect.soft(summarize(result.violations)).toEqual([]);
  expect
    .soft(await page.evaluate(() => document.documentElement.scrollWidth))
    .toBeLessThanOrEqual(page.viewportSize()!.width + 1);
}

test("invitations: independent active fixture, cancel, revoke and refresh", async ({
  page,
}) => {
  await signIn(page);
  await page.goto(`/roles/${role}`);
  await page.getByRole("link", { name: /invitation/i }).click();
  await expect(page).toHaveURL(new RegExp(`${invitations}$`));
  const row = page.getByRole("listitem").filter({
    has: page.getByRole("heading", {
      name: "revoke@example.invalid",
      exact: true,
    }),
  });
  await expect(row.getByText("Stored invitation state: Active")).toBeVisible();
  for (const width of [320, 375, 1280]) {
    await page.setViewportSize({ width, height: 800 });
    await inspect(page);
  }
  const revoke = row.getByRole("button", {
    name: "Revoke invitation for revoke@example.invalid",
  });
  page.once("dialog", async (dialog) => {
    expect(dialog.type()).toBe("confirm");
    await dialog.dismiss();
  });
  await revoke.click();
  await expect(row.getByText("Stored invitation state: Active")).toBeVisible();
  page.once("dialog", async (dialog) => {
    expect(dialog.type()).toBe("confirm");
    await dialog.accept();
  });
  await revoke.click();
  await expect(row.getByText("Stored invitation state: Revoked")).toBeVisible();
  await expect(revoke).toHaveCount(0);
  await expect(
    page
      .getByRole("status")
      .filter({ hasText: "Invitation status refreshed after revocation." }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Refresh invitation history" })
    .click();
  await expect(row.getByText("Stored invitation state: Revoked")).toBeVisible();
  await page.reload();
  await expect(row.getByText("Stored invitation state: Revoked")).toBeVisible();
  await inspect(page);
  await page.goto(`/candidate/invites/${process.env.BROWSER_E2E_REVOKE}`);
  await expect(
    page.getByRole("heading", { name: "We could not open this assessment" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "I consent and want to begin" }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("navigation", { name: "Primary navigation" }),
  ).toHaveCount(0);
});

test("account navigation: identity, invitation return path and sign-out boundary", async ({
  page,
}) => {
  await signIn(page);
  await page.goto(invitations);
  const nav = page.getByRole("navigation", { name: "Primary navigation" });
  await expect(
    nav.getByText("Alpha Recruiter · recruiter", { exact: true }),
  ).toBeVisible();
  await expect(
    nav.getByText("Organization: 00000000-0000-4000-8000-000000000001", {
      exact: true,
    }),
  ).toBeVisible();
  await nav.getByRole("button", { name: "Sign out" }).focus();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(
    (url) =>
      url.pathname === "/sign-in" &&
      url.searchParams.get("returnTo") === invitations,
  );
  expect(
    await page.evaluate(
      async () => (await fetch("/api/internal/roles")).status,
    ),
  ).toBe(401);
  // The sign-out URL above carries the safe return path. Synthetic exchange
  // only establishes the cookie; provider callback navigation has separate tests.
  expect(await exchangeSession(page, process.env.BROWSER_E2E_RECRUITER!)).toBe(
    200,
  );
  await page.goto(invitations);
  await expect(page).toHaveURL(new RegExp(`${invitations}$`));
  await expect(nav.getByRole("button", { name: "Sign out" })).toBeVisible();
  await nav.getByRole("link", { name: "Roles", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Organization roles" }),
  ).toBeVisible();
});

test("manager invitation denial retains separate account context", async ({
  page,
}) => {
  await signIn(page, "MANAGER");
  await page.goto("/roles/00000000-0000-4000-8000-000000000022/invites");
  await expect(page.getByRole("main").getByRole("alert")).toHaveText(
    "Only recruiters and administrators can manage invitations.",
  );
  await expect(
    page
      .getByRole("navigation")
      .getByText("Beacon Manager · hiring manager", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: /^Revoke invitation/ }),
  ).toHaveCount(0);
  await inspect(page);
});
