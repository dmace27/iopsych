import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
import AxeBuilder from "@axe-core/playwright";

const definition = JSON.parse(
  readFileSync(
    new URL(
      "../../packages/shared/definitions/v1/pilot-assessment.json",
      import.meta.url,
    ),
    "utf8",
  ),
);
const answers = {
  assessment_definition_id: definition.id,
  assessment_definition_version: definition.version,
  responses: definition.blocks.map(
    (block: { id: string; items: { id: string }[] }) => ({
      block_id: block.id,
      skipped: false,
      most_like_item_id: block.items[0].id,
      least_like_item_id: block.items[1].id,
    }),
  ),
};

const invite = `/candidate/invites/${process.env.BROWSER_E2E_INVITE}`;

test.beforeEach(async ({ context }) => {
  await context.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (url.origin !== "http://127.0.0.1:3104") {
      throw new Error("Browser attempted a nonlocal or unowned request");
    }
    await route.continue();
  });
});

async function accessible(page: import("@playwright/test").Page) {
  const result = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
    .analyze();
  expect(
    result.violations.map((v) => ({
      id: v.id,
      impact: v.impact,
      targets: v.nodes.map((n) => n.target),
    })),
  ).toEqual([]);
}

test("production health and unauthenticated internal boundary", async ({
  page,
}) => {
  const response = await page.goto("/api/health");
  expect(response?.status()).toBe(200);
  const status = await page.evaluate(
    async () => (await fetch("/api/internal/roles")).status,
  );
  expect(status).toBe(401);
});

test("public sign-in is accessible and rejects invalid credentials", async ({
  page,
}) => {
  await page.goto("/sign-in");
  await expect(
    page.getByRole("heading", { name: "Sign in to Role studio" }),
  ).toBeVisible();
  await accessible(page);
  await page
    .getByLabel("Internal access token")
    .fill("synthetic-invalid-token");
  await page.getByRole("button", { name: "Continue to roles" }).click();
  await expect(page.getByRole("alert")).toBeVisible();
  await expect(page).toHaveURL(/\/sign-in$/);
  expect(await page.context().cookies()).toEqual([]);
});

test("consent gates questions and decline survives refresh", async ({
  page,
}) => {
  await page.goto(invite);
  await expect(
    page.getByRole("heading", { name: "Your choice and your data" }),
  ).toBeVisible();
  await expect(page.getByRole("radio")).toHaveCount(0);
  await accessible(page);
  const status = await page.evaluate(
    async ({ token, answers }) => {
      const response = await fetch(`/api/candidate/invites/${token}/submit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(answers),
      });
      return response.status;
    },
    { token: process.env.BROWSER_E2E_INVITE, answers },
  );
  expect(status).toBe(409);
  await page.getByRole("button", { name: "I decline", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "You declined the assessment" }),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "You declined the assessment" }),
  ).toBeVisible();
  await expect(page.getByRole("radio")).toHaveCount(0);
  await accessible(page);
});
