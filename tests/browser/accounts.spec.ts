import { test, expect, type Page, type Locator } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const origin = "http://127.0.0.1:3116";
const targetId = "00000000-0000-4000-8000-000000000098";
const adminId = "00000000-0000-4000-8000-000000000099";
const endpoint = "/api/internal/accounts/users";

test.beforeEach(async ({ context }) => {
  await context.route("**/*", async (route) => {
    if (new URL(route.request().url()).origin !== origin)
      throw new Error("Account browser attempted an unowned request");
    await route.continue();
  });
});

async function signIn(page: Page, identity = "ADMIN") {
  await page.goto("/sign-in");
  await page
    .getByLabel("Internal access token")
    .fill(process.env[`BROWSER_E2E_${identity}`]!);
  await page.getByRole("button", { name: "Continue to roles" }).click();
  await expect(
    page.getByRole("heading", { name: "Organization roles" }),
  ).toBeVisible();
}

async function tabTo(page: Page, target: Locator) {
  for (let step = 0; step < 100; step++) {
    if (await target.evaluate((element) => element === document.activeElement))
      return;
    await page.keyboard.press("Tab");
  }
  throw new Error("Account control was not keyboard reachable");
}

async function scan(page: Page, state: string) {
  const result = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
    .analyze();
  const summarize = (items: typeof result.violations) =>
    items.map((item) => ({ id: item.id, nodes: item.nodes.length }));
  console.log(
    "ACCOUNTS_AXE " +
      JSON.stringify({
        state,
        axe: result.testEngine.version,
        browser: page.context().browser()?.version(),
        violations: summarize(result.violations),
        incomplete: summarize(result.incomplete),
      }),
  );
  expect.soft(summarize(result.violations)).toEqual([]);
}

async function currentAccount(page: Page) {
  const response = await page.request.get(endpoint);
  expect(response.status()).toBe(200);
  const body = await response.json();
  return body.items.find((item: { id: string }) => item.id === targetId);
}

function targetRow(page: Page) {
  return page
    .getByRole("list", { name: "Organization accounts" })
    .getByRole("listitem")
    .filter({
      has: page.getByRole("heading", {
        name: "Synthetic account target",
        exact: true,
      }),
    });
}

async function confirmChange(page: Page, update: Record<string, unknown>) {
  const dialog = page.getByRole("alertdialog", {
    name: "Confirm access change",
  });
  await expect(
    dialog.getByRole("button", { name: "Cancel", exact: true }),
  ).toBeFocused();
  const responsePromise = page.waitForResponse(
    (response) =>
      response.url().endsWith(`${endpoint}/${targetId}`) &&
      response.request().method() === "PATCH",
  );
  await page.keyboard.press("Tab");
  await expect(
    dialog.getByRole("button", { name: "Confirm change" }),
  ).toBeFocused();
  await page.keyboard.press("Enter");
  const response = await responsePromise;
  expect(response.request().postDataJSON()).toEqual(update);
  expect(response.status()).toBe(200);
  const result = await response.json();
  expect(result.version).toBe(Number(update.expected_version) + 1);
  await expect(page.getByRole("status")).toHaveText(
    "Access updated for Synthetic account target.",
  );
  await expect(page.getByRole("status").locator("..")).toBeFocused();
  return result;
}

test("admin discovers accounts, changes versioned access and enforces disabled fresh authentication", async ({
  page,
  context,
}) => {
  await signIn(page);
  await page.getByRole("link", { name: "Accounts", exact: true }).click();
  const row = targetRow(page);
  await expect(row).toBeVisible();
  await expect(page.getByText("beacon", { exact: false })).toHaveCount(0);
  const initial = await currentAccount(page);
  expect(initial).toMatchObject({ role: "recruiter", is_active: true });
  await scan(page, "discovery");

  const member = await context.browser()!.newContext({ baseURL: origin });
  await member.route("**/*", async (route) => {
    if (new URL(route.request().url()).origin !== origin)
      throw new Error("Unowned member request");
    await route.continue();
  });
  try {
    const memberPage = await member.newPage();
    await signIn(memberPage, "ACCOUNT");
    await row
      .getByLabel("Role for Synthetic account target")
      .selectOption("hiring_manager");
    const review = row.getByRole("button", { name: "Review role change" });
    await tabTo(page, review);
    await page.keyboard.press("Enter");
    await scan(page, "role confirmation");
    await page.keyboard.press("Escape");
    await expect(review).toBeFocused();
    expect((await currentAccount(page)).version).toBe(initial.version);
    await page.keyboard.press("Enter");
    const changed = await confirmChange(page, {
      expected_version: initial.version,
      role: "hiring_manager",
    });
    const me = await memberPage.request.get("/api/internal/auth/me");
    expect(me.status()).toBe(200);
    expect((await me.json()).role).toBe("hiring_manager");

    await tabTo(
      page,
      row.getByRole("button", { name: "Deactivate", exact: true }),
    );
    await page.keyboard.press("Enter");
    const disabled = await confirmChange(page, {
      expected_version: changed.version,
      is_active: false,
    });
    await expect(
      row.getByText("hiring manager · Inactive", { exact: true }),
    ).toBeVisible();
    expect(
      (await memberPage.request.get("/api/internal/auth/me")).status(),
    ).toBe(401);
    await member.clearCookies();
    await memberPage.goto("/sign-in");
    await memberPage
      .getByLabel("Internal access token")
      .fill(process.env.BROWSER_E2E_ACCOUNT!);
    const rejected = memberPage.waitForResponse(
      (response) =>
        response.url() === `${origin}/api/session` &&
        response.request().method() === "POST",
    );
    await memberPage.getByRole("button", { name: "Continue to roles" }).click();
    expect((await rejected).status()).toBe(401);
    await expect(memberPage.getByRole("main").getByRole("alert")).toBeVisible();
    expect(
      (await member.cookies()).filter((cookie) => cookie.httpOnly),
    ).toHaveLength(0);
    await scan(page, "inactive account");

    await tabTo(
      page,
      row.getByRole("button", { name: "Reactivate", exact: true }),
    );
    await page.keyboard.press("Enter");
    const active = await confirmChange(page, {
      expected_version: disabled.version,
      is_active: true,
    });
    await signIn(memberPage, "ACCOUNT");
    expect(
      (await memberPage.request.get("/api/internal/auth/me")).status(),
    ).toBe(200);
    await row
      .getByLabel("Role for Synthetic account target")
      .selectOption("recruiter");
    await row.getByRole("button", { name: "Review role change" }).click();
    await confirmChange(page, {
      expected_version: active.version,
      role: "recruiter",
    });
    await page.reload();
    await expect(
      row.getByText("recruiter · Active", { exact: true }),
    ).toBeVisible();
  } finally {
    await member.close();
  }
});

test("admin self is read-only and stale browser review requires refreshed values", async ({
  page,
  context,
}) => {
  await signIn(page);
  await page.goto("/accounts");
  const self = page.getByRole("listitem").filter({
    has: page.getByRole("heading", {
      name: "Synthetic browser admin (you)",
      exact: true,
    }),
  });
  await expect(self.getByText(/Your account is read-only/)).toBeVisible();
  await expect(self.getByRole("button")).toHaveCount(0);
  await expect(self.getByRole("combobox")).toHaveCount(0);
  const denied = await page.request.patch(`${endpoint}/${adminId}`, {
    headers: { Origin: origin },
    data: { expected_version: 1, is_active: false },
  });
  expect(denied.status()).toBe(403);
  const initial = await currentAccount(page);
  const stale = await context.newPage();
  await stale.goto("/accounts");
  await targetRow(stale)
    .getByLabel("Role for Synthetic account target")
    .selectOption(
      initial.role === "hiring_manager" ? "recruiter" : "hiring_manager",
    );
  await targetRow(stale)
    .getByRole("button", { name: "Review role change" })
    .click();
  await targetRow(page)
    .getByLabel("Role for Synthetic account target")
    .selectOption("admin");
  await targetRow(page)
    .getByRole("button", { name: "Review role change" })
    .click();
  const changed = await confirmChange(page, {
    expected_version: initial.version,
    role: "admin",
  });
  const conflict = stale.waitForResponse(
    (response) =>
      response.url().endsWith(`${endpoint}/${targetId}`) &&
      response.request().method() === "PATCH",
  );
  await stale.getByRole("button", { name: "Confirm change" }).click();
  expect((await conflict).status()).toBe(409);
  await expect(stale.getByRole("main").getByRole("alert")).toContainText(
    "Account details changed.",
  );
  await expect(targetRow(stale).getByRole("combobox")).toBeDisabled();
  await scan(stale, "stale conflict");
  await stale.getByRole("button", { name: "Refresh accounts" }).click();
  await expect(targetRow(stale).getByRole("combobox")).toHaveValue("admin");
  await expect(targetRow(stale).getByRole("combobox")).toBeEnabled();
  await targetRow(stale).getByRole("combobox").selectOption("recruiter");
  await targetRow(stale)
    .getByRole("button", { name: "Review role change" })
    .click();
  await confirmChange(stale, {
    expected_version: changed.version,
    role: "recruiter",
  });
  await stale.close();
});

test("manager is denied account discovery and mutations in browser and API", async ({
  page,
}) => {
  await signIn(page, "MANAGER");
  await expect(
    page.getByRole("link", { name: "Accounts", exact: true }),
  ).toHaveCount(0);
  await page.goto("/accounts");
  await expect(page.getByRole("main").getByRole("alert")).toHaveText(
    "Only administrators can manage accounts.",
  );
  await expect(
    page.getByRole("list", { name: "Organization accounts" }),
  ).toHaveCount(0);
  expect((await page.request.get(endpoint)).status()).toBe(403);
  expect(
    (
      await page.request.patch(`${endpoint}/${targetId}`, {
        headers: { Origin: origin },
        data: { expected_version: 1, is_active: false },
      })
    ).status(),
  ).toBe(403);
  await scan(page, "manager denial");
});
