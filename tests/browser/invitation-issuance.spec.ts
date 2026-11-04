import { syntheticSignIn } from "./auth";
import { randomUUID } from "node:crypto";
import { test, expect, type Page, type Locator } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const origin = "http://127.0.0.1:3116";
const role = "00000000-0000-4000-8000-000000000021";
const profile = "00000000-0000-4000-8000-000000000031";
const path = `/roles/${role}/invites`;
const endpoint = `/api/internal${path}`;
const recipient = () => `issuance-${randomUUID()}@example.invalid`;
const form = (page: Page) =>
  page.getByRole("region", { name: "Issue invitation", exact: true });
const row = (page: Page, email: string) =>
  page.getByRole("listitem").filter({
    has: page.getByRole("heading", { name: email, exact: true }),
  });

test.beforeEach(async ({ context }) => {
  await context.route("**/*", async (route) => {
    if (new URL(route.request().url()).origin !== origin)
      throw new Error("Invitation browser attempted an unowned request");
    await route.continue();
  });
});

async function signIn(page: Page, identity = "RECRUITER") {
  await syntheticSignIn(page, identity);
  await expect(
    page.getByRole("heading", { name: "Organization roles" }),
  ).toBeVisible();
}

async function prepare(page: Page, email: string, expiry = "") {
  await form(page).getByLabel("Recipient email").fill(email);
  await form(page).getByLabel("Approved profile version").selectOption(profile);
  await form(page)
    .getByLabel("Requested expiry in hours (optional)")
    .fill(expiry);
}

async function confirm(page: Page) {
  const response = page.waitForResponse(
    (response) =>
      new URL(response.url()).pathname === endpoint &&
      response.request().method() === "POST",
  );
  await form(page)
    .getByRole("button", { name: "Confirm and issue invitation", exact: true })
    .click();
  expect((await response).status()).toBe(201);
  await expect(form(page).getByRole("status")).toContainText(
    "Invitation recorded. Stored status:",
  );
  await expect(form(page).getByRole("status")).toContainText(
    "Delivery receipt is not confirmed here.",
  );
}

async function tabTo(page: Page, target: Locator) {
  for (let step = 0; step < 100; step++) {
    if (await target.evaluate((element) => element === document.activeElement))
      return;
    await page.keyboard.press("Tab");
  }
  throw new Error(
    "Invitation control was not reachable within 100 Tab presses",
  );
}

async function scan(page: Page) {
  const result = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
    .analyze();
  const summarize = (items: typeof result.violations) =>
    items.map((item) => ({ id: item.id, nodes: item.nodes.length }));
  console.log(
    "ISSUANCE_AXE " +
      JSON.stringify({
        test: test.info().title,
        width: page.viewportSize()?.width,
        browser: page.context().browser()?.version(),
        axe: result.testEngine.version,
        violations: summarize(result.violations),
        incomplete: summarize(result.incomplete),
      }),
  );
  expect.soft(summarize(result.violations)).toEqual([]);
  expect
    .soft(await page.evaluate(() => document.documentElement.scrollWidth))
    .toBeLessThanOrEqual(page.viewportSize()!.width + 1);
}

test("issuance: approved version preview requires explicit confirmation", async ({
  page,
}) => {
  await signIn(page);
  await page.goto(path);
  const profiles = await page.evaluate(async (roleId) => {
    const response = await fetch(`/api/internal/roles/${roleId}/profiles`);
    if (!response.ok) throw new Error("Synthetic profiles could not be loaded");
    return (await response.json()) as { id: string; status: string }[];
  }, role);
  const approved = profiles.filter((item) => item.status === "approved");
  await expect(
    form(page).getByLabel("Approved profile version").getByRole("option"),
  ).toHaveCount(approved.length + 1);
  expect(
    await form(page)
      .getByLabel("Approved profile version")
      .locator("option")
      .evaluateAll((options) =>
        options
          .map((option) => (option as HTMLOptionElement).value)
          .filter(Boolean),
      ),
  ).toEqual(approved.map((item) => item.id));
  const email = recipient();
  const posts: { body: unknown; key: string | undefined }[] = [];
  page.on("request", (request) => {
    if (
      new URL(request.url()).pathname === endpoint &&
      request.method() === "POST"
    )
      posts.push({
        body: request.postDataJSON(),
        key: request.headers()["idempotency-key"],
      });
  });
  await prepare(page, email, "24");
  await expect(
    form(page).getByRole("button", { name: "Confirm and issue invitation" }),
  ).toHaveCount(0);
  await form(page).getByRole("button", { name: "Review invitation" }).click();
  await expect(
    form(page).getByText(`Recipient: ${email}`, { exact: true }),
  ).toBeVisible();
  await expect(
    form(page).getByText(`Profile version: 1 (${profile})`, { exact: true }),
  ).toBeVisible();
  await expect(
    form(page).getByText("Requested expiry: 24 hours from issuance", {
      exact: true,
    }),
  ).toBeVisible();
  expect(posts).toHaveLength(0);
  await confirm(page);
  expect(posts).toHaveLength(1);
  expect(posts[0].body).toEqual({
    role_profile_id: profile,
    email,
    expires_in_hours: 24,
  });
  expect(posts[0].key).toMatch(/^[0-9a-f-]{36}$/);
  await expect(row(page, email)).toHaveCount(1);
  await expect(
    row(page, email).getByText(`Profile ID: ${profile}`, { exact: true }),
  ).toBeVisible();
  await page.reload();
  await expect(row(page, email)).toHaveCount(1);
});

test("issuance: double click sends one browser request while confirmation is pending", async ({
  page,
}) => {
  await signIn(page);
  await page.goto(path);
  const email = recipient();
  await prepare(page, email);
  await form(page).getByRole("button", { name: "Review invitation" }).click();
  let posts = 0;
  let release!: () => void;
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route(`**${endpoint}`, async (route) => {
    if (route.request().method() === "POST") {
      posts++;
      await gate;
    }
    await route.fallback();
  });
  try {
    const button = form(page).getByRole("button", {
      name: "Confirm and issue invitation",
      exact: true,
    });
    await button.scrollIntoViewIfNeeded();
    const box = await button.boundingBox();
    expect(box).not.toBeNull();
    await page.mouse.dblclick(
      box!.x + box!.width / 2,
      box!.y + box!.height / 2,
    );
    await expect(
      form(page).getByRole("button", { name: "Issuing invitation…" }),
    ).toBeDisabled();
    await expect(
      page.getByRole("button", { name: "Refresh invitation history" }),
    ).toBeDisabled();
    await expect.poll(() => posts).toBe(1);
  } finally {
    release();
  }
  await expect(form(page).getByRole("status")).toContainText(
    "Invitation recorded.",
  );
  expect(posts).toBe(1);
  await expect(row(page, email)).toHaveCount(1);
  await expect(
    form(page).getByRole("button", {
      name: "Confirm and issue invitation",
      exact: true,
    }),
  ).toBeDisabled();
});

test("issuance: invalid expiry blocks preview and server rejects bypass", async ({
  page,
}) => {
  await signIn(page);
  await page.goto(path);
  const email = recipient();
  await prepare(page, email);
  for (const expiry of ["0", "721", "1.5"]) {
    await form(page)
      .getByLabel("Requested expiry in hours (optional)")
      .fill(expiry);
    await expect(
      form(page).getByRole("button", { name: "Review invitation" }),
    ).toBeDisabled();
    await expect(
      form(page).getByRole("button", { name: "Confirm and issue invitation" }),
    ).toHaveCount(0);
  }
  const status = await page.evaluate(
    async ({ endpoint, profile, email }) => {
      const response = await fetch(endpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": crypto.randomUUID(),
        },
        body: JSON.stringify({
          role_profile_id: profile,
          email,
          expires_in_hours: 721,
        }),
      });
      return response.status;
    },
    { endpoint, profile, email },
  );
  expect(status).toBe(422);
  await page.reload();
  await expect(form(page).getByLabel("Recipient email")).toBeVisible();
  await expect(row(page, email)).toHaveCount(0);
});

test("issuance: manager is denied in the UI and same-organization POST", async ({
  page,
}) => {
  await signIn(page, "MANAGER");
  const managerRole = "00000000-0000-4000-8000-000000000022";
  await page.goto(`/roles/${managerRole}/invites`);
  await expect(page.getByRole("main").getByRole("alert")).toHaveText(
    "Only recruiters and administrators can manage invitations.",
  );
  await expect(form(page)).toHaveCount(0);
  const status = await page.evaluate(
    async ({ managerRole, email }) => {
      const response = await fetch(
        `/api/internal/roles/${managerRole}/invites`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Idempotency-Key": crypto.randomUUID(),
          },
          body: JSON.stringify({
            role_profile_id: "00000000-0000-4000-8000-000000000032",
            email,
          }),
        },
      );
      return response.status;
    },
    { managerRole, email: recipient() },
  );
  expect(status).toBe(403);
  await scan(page);
});

test("issuance: revoke preserves keyboard focus and explicit new issuance uses a new key", async ({
  page,
}) => {
  await signIn(page);
  await page.goto(path);
  const email = recipient();
  const keys: string[] = [];
  page.on("request", (request) => {
    if (
      new URL(request.url()).pathname === endpoint &&
      request.method() === "POST"
    )
      keys.push(request.headers()["idempotency-key"]);
  });
  await prepare(page, email);
  await form(page).getByRole("button", { name: "Review invitation" }).click();
  await expect(
    form(page).getByText("Requested expiry: Server default", { exact: true }),
  ).toBeVisible();
  await confirm(page);
  const first = row(page, email);
  const revoke = first.getByRole("button", {
    name: `Revoke invitation for ${email}`,
  });
  await tabTo(page, revoke);
  page.once("dialog", async (dialog) => {
    await dialog.accept();
  });
  await page.keyboard.press("Enter");
  await expect(
    first.getByText("Stored invitation state: Revoked"),
  ).toBeVisible();
  await expect(first).toBeFocused();
  await form(page)
    .getByRole("button", { name: "Start new invitation" })
    .click();
  await expect(form(page).getByLabel("Recipient email")).toHaveValue("");
  await expect(
    form(page).getByRole("button", { name: "Confirm and issue invitation" }),
  ).toHaveCount(0);
  await prepare(page, email);
  await form(page).getByRole("button", { name: "Review invitation" }).click();
  await confirm(page);
  expect(keys).toHaveLength(2);
  expect(keys[0]).not.toBe(keys[1]);
  await expect(row(page, email)).toHaveCount(2);
  await expect(
    row(page, email).filter({ hasText: "Stored invitation state: Revoked" }),
  ).toHaveCount(1);
  await page.reload();
  await expect(row(page, email)).toHaveCount(2);
});

test("issuance: keyboard preview and axe at narrow and desktop widths", async ({
  page,
}) => {
  await signIn(page);
  await page.goto(path);
  await prepare(page, recipient(), "24");
  const review = form(page).getByRole("button", { name: "Review invitation" });
  await tabTo(page, review);
  await page.keyboard.press("Enter");
  await page.keyboard.press("Tab");
  await expect(
    form(page).getByRole("button", {
      name: "Confirm and issue invitation",
      exact: true,
    }),
  ).toBeFocused();
  for (const width of [320, 375, 1280]) {
    await page.setViewportSize({ width, height: 800 });
    await scan(page);
  }
  await page.keyboard.press("Shift+Tab");
  await expect(review).toBeFocused();
});
