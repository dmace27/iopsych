import { syntheticSignIn } from "./auth";
import { test, expect, type Page, type Locator } from "@playwright/test";
import { readFileSync } from "node:fs";

const alphaRole = "00000000-0000-4000-8000-000000000021";
const beaconRole = "00000000-0000-4000-8000-000000000022";
const description =
  "Synthetic work involves planning, shared learning, and changing priorities.";
const definition = JSON.parse(
  readFileSync(
    new URL(
      "../../packages/shared/definitions/v1/pilot-assessment.json",
      import.meta.url,
    ),
    "utf8",
  ),
);

test.beforeEach(async ({ context }) => {
  await context.route("**/*", async (route) => {
    if (new URL(route.request().url()).origin !== "http://127.0.0.1:3116")
      throw new Error("Maintenance browser attempted an unowned request");
    await route.continue();
  });
});

async function tabTo(page: Page, target: Locator) {
  for (let step = 0; step < 100; step++) {
    if (await target.evaluate((element) => element === document.activeElement))
      return;
    await page.keyboard.press("Tab");
  }
  throw new Error("Named action was not reachable within 100 Tab presses");
}

async function signIn(page: Page, identity = "RECRUITER") {
  await syntheticSignIn(page, identity);
  await expect(
    page.getByRole("heading", { name: "Organization roles" }),
  ).toBeVisible();
}

test("recruiter maintains an independent role, preserves versions and archives read-only", async ({
  page,
}) => {
  await signIn(page);
  await page.getByRole("button", { name: "Create role", exact: true }).click();
  await page.getByLabel("Role title").fill("Synthetic maintenance-only role");
  await page
    .getByLabel("Department", { exact: true })
    .fill("Synthetic testing");
  await page.getByLabel("Location", { exact: true }).fill("Local only");
  await page.getByLabel("Job description").fill(description);
  await page.getByRole("button", { name: "Create draft role" }).click();
  await expect(
    page.getByRole("heading", {
      name: "Synthetic maintenance-only role",
      exact: true,
    }),
  ).toBeVisible();
  const maintenance = page.getByRole("region", { name: "Role maintenance" });
  await maintenance.getByRole("button", { name: "Edit role details" }).click();
  await expect(maintenance.getByLabel(/Job description/)).toBeEditable();
  await maintenance.getByLabel(/Role title/).fill("Synthetic maintained role");
  await maintenance.getByRole("button", { name: "Save role details" }).click();
  await expect(maintenance.getByRole("heading")).toBeFocused();
  await expect(
    page.getByRole("heading", {
      name: "Synthetic maintained role",
      exact: true,
    }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Extract profile from job description" })
    .click();
  await expect(
    page.getByText(
      "Synthetic fixture; no scientific or human approval implied.",
    ),
  ).toBeVisible();
  await page.getByRole("button", { name: "Save new version" }).click();
  await expect(page.getByRole("button", { name: /Version 2/ })).toBeVisible();
  await maintenance.getByRole("button", { name: "Edit role details" }).click();
  await expect(maintenance.getByLabel(/Job description/)).toBeDisabled();
  await expect(maintenance.getByLabel(/Job description/)).toHaveValue(
    description,
  );
  await maintenance
    .getByLabel(/Department/)
    .fill("Synthetic updated department");
  await maintenance.getByLabel(/Location/).fill("Synthetic updated location");
  await maintenance.getByRole("button", { name: "Save role details" }).click();
  await expect(maintenance.getByRole("heading")).toBeFocused();
  await page.reload();
  await expect(page.getByRole("button", { name: /Version 1/ })).toBeVisible();
  await expect(page.getByRole("button", { name: /Version 2/ })).toBeVisible();
  await maintenance.getByRole("button", { name: "Edit role details" }).click();
  await expect(maintenance.getByLabel(/Department/)).toHaveValue(
    "Synthetic updated department",
  );
  await expect(maintenance.getByLabel(/Location/)).toHaveValue(
    "Synthetic updated location",
  );
  await expect(maintenance.getByLabel(/Job description/)).toBeDisabled();
  await maintenance.getByRole("button", { name: "Cancel editing" }).click();
  await expect(maintenance.getByRole("heading")).toBeFocused();
  const archive = maintenance.getByRole("button", {
    name: "Archive role",
    exact: true,
  });
  await tabTo(page, archive);
  await page.keyboard.press("Enter");
  const dialog = page.getByRole("dialog", {
    name: "Archive Synthetic maintained role?",
  });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole("button", { name: "Keep role" })).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(
    dialog.getByRole("button", { name: "Confirm archive" }),
  ).toBeFocused();
  await page.keyboard.press("Shift+Tab");
  await expect(dialog.getByRole("button", { name: "Keep role" })).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(dialog).not.toBeVisible();
  await expect(archive).toBeFocused();
  await page.keyboard.press("Enter");
  await page.keyboard.press("Tab");
  await page.keyboard.press("Enter");
  await expect(
    maintenance.getByText("This archived role is read-only."),
  ).toBeVisible();
  await expect(maintenance.getByRole("heading")).toBeFocused();
  await expect(maintenance.getByRole("button")).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Save new version" }),
  ).toHaveCount(0);
  await page.reload();
  await expect(
    maintenance.getByText("This archived role is read-only."),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: /Version 1/ })).toBeVisible();
  await expect(page.getByRole("button", { name: /Version 2/ })).toBeVisible();
});

test("manager sees maintenance denial and cannot patch or archive their own tenant role", async ({
  page,
}) => {
  await signIn(page, "MANAGER");
  await page.goto(`/roles/${beaconRole}`);
  const maintenance = page.getByRole("region", { name: "Role maintenance" });
  await expect(
    maintenance.getByText(
      "Only administrators and recruiters can edit details or archive this role.",
    ),
  ).toBeVisible();
  await expect(maintenance.getByRole("button")).toHaveCount(0);
  const statuses = await page.evaluate(async (id) => {
    const update = await fetch(`/api/internal/roles/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: "Synthetic unauthorized change" }),
    });
    const archive = await fetch(`/api/internal/roles/${id}`, {
      method: "DELETE",
    });
    return [update.status, archive.status];
  }, beaconRole);
  expect(statuses).toEqual([403, 403]);
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Synthetic Program Lead", exact: true }),
  ).toBeVisible();
  await page.goto("/privacy");
  await expect(
    page.getByRole("heading", { name: "Administrator access required" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Find assessments" }),
  ).toHaveCount(0);
});

test("administrator discovers an independent assessment and keeps anonymization lifecycle truthful", async ({
  page,
}) => {
  await page.goto(`/candidate/invites/${process.env.BROWSER_E2E_PRIVACY}`);
  await page
    .getByRole("button", { name: "I consent and want to begin" })
    .click();
  for (let block = 1; block <= definition.blocks.length; block++) {
    await expect(
      page.getByText(`Block ${block} of ${definition.blocks.length}`, {
        exact: true,
      }),
    ).toBeVisible();
    await page
      .getByRole("radio", { name: /^Most like me:/ })
      .nth(0)
      .check();
    await page
      .getByRole("radio", { name: /^Least like me:/ })
      .nth(1)
      .check();
    await page
      .getByRole("button", {
        name:
          block === definition.blocks.length ? "Review answers" : "Continue",
        exact: true,
      })
      .click();
  }
  await page.getByRole("button", { name: "Submit my responses" }).click();
  await expect(
    page.getByRole("heading", { name: "Your responses are complete" }),
  ).toBeVisible();
  await signIn(page, "ADMIN");
  await page.goto("/privacy");
  await page.getByLabel("Reference type").selectOption("role_id");
  await page.getByLabel("Reference ID", { exact: true }).fill(alphaRole);
  await page.getByRole("button", { name: "Find assessments" }).click();
  const selection = page.getByRole("button", { name: /^Select assessment / });
  await expect(selection).toHaveCount(1);
  await tabTo(page, selection);
  await page.keyboard.press("Enter");
  const assessmentId = await page
    .getByLabel("Assessment ID", { exact: true })
    .inputValue();
  expect(assessmentId).toMatch(/^[0-9a-f-]{36}$/);
  const row = page.getByRole("listitem").filter({ has: selection });
  await expect(row.getByText("Anonymized: No", { exact: true })).toBeVisible();
  await expect(selection).toHaveAttribute("aria-pressed", "true");
  await page.getByRole("button", { name: "Create JSON export" }).click();
  const downloadLink = page.getByRole("link", { name: "Download JSON export" });
  await expect(downloadLink).toBeVisible();
  const downloading = page.waitForEvent("download");
  await downloadLink.click();
  const download = await downloading;
  expect(await download.failure()).toBeNull();
  await download.delete();
  await page.getByRole("button", { name: "Prepare anonymization" }).click();
  await page.getByRole("button", { name: "Cancel anonymization" }).click();
  await expect(
    page.getByRole("button", { name: "Confirm anonymization" }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "Prepare anonymization" }).click();
  await page.getByRole("button", { name: "Confirm anonymization" }).click();
  await expect(
    page.getByText(`Assessment ${assessmentId} was anonymized.`, {
      exact: false,
    }),
  ).toBeVisible();
  await expect(downloadLink).toHaveCount(0);
  await expect(row.getByText("Anonymized: No", { exact: true })).toHaveCount(0);
  await expect(
    page
      .locator('[aria-live="polite"]')
      .filter({ hasText: "Candidate data was anonymized." }),
  ).toHaveText("Candidate data was anonymized.");
  await page.getByRole("button", { name: "Create JSON export" }).click();
  await expect(page.getByRole("alert")).toBeVisible();
  await expect(downloadLink).toHaveCount(0);
  await expect(
    page
      .locator('[aria-live="polite"]')
      .filter({ hasText: "Candidate data export created." }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "Find assessments" }).click();
  await expect(page.getByLabel("Assessment ID", { exact: true })).toHaveValue(
    "",
  );
  await expect(
    page.getByRole("button", { name: "Create JSON export" }),
  ).toBeDisabled();
  await expect(row.getByText("Anonymized: No", { exact: true })).toHaveCount(0);
  await expect(
    page.getByText(`Assessment ${assessmentId} was anonymized.`, {
      exact: false,
    }),
  ).toHaveCount(0);
});

test("keyboard invitation revocation retains useful focus after its action disappears", async ({
  page,
}) => {
  await signIn(page);
  await page.goto(`/roles/${alphaRole}/invites`);
  const row = page.getByRole("listitem").filter({
    has: page.getByRole("heading", {
      name: "focus@example.invalid",
      exact: true,
    }),
  });
  const revoke = row.getByRole("button", {
    name: "Revoke invitation for focus@example.invalid",
  });
  await tabTo(page, revoke);
  page.once("dialog", (dialog) => dialog.dismiss());
  await page.keyboard.press("Enter");
  await expect(revoke).toBeFocused();
  await expect(row.getByText("Stored invitation state: Active")).toBeVisible();
  page.once("dialog", (dialog) => dialog.accept());
  await page.keyboard.press("Enter");
  await expect(row.getByText("Stored invitation state: Revoked")).toBeVisible();
  await expect(revoke).toHaveCount(0);
  await expect(row).toBeFocused();
  await page.keyboard.press("Tab");
  expect(
    await page.evaluate(() =>
      document.activeElement?.matches(
        "button, a[href], input, select, textarea",
      ),
    ),
  ).toBe(true);
});

test("keyboard final invitation pagination focuses the first appended record", async ({
  page,
}) => {
  await signIn(page);
  await page.goto(`/roles/${alphaRole}/invites`);
  const response = await page.request.get(
    `/api/internal/roles/${alphaRole}/invites?limit=100`,
  );
  expect(response.status()).toBe(200);
  const total = (await response.json()).items.length;
  expect(total).toBeGreaterThan(25);
  expect(total).toBeLessThanOrEqual(50);
  const rows = page.getByRole("main").getByRole("listitem");
  await expect(rows).toHaveCount(25);
  const more = page.getByRole("button", { name: "Load more invitations" });
  await tabTo(page, more);
  await page.keyboard.press("Enter");
  await expect(rows).toHaveCount(total);
  await expect(more).toHaveCount(0);
  await expect(rows.nth(25)).toBeFocused();
  await expect(
    page
      .getByRole("status")
      .filter({ hasText: `${total - 25} more invitations loaded.` }),
  ).toBeVisible();
});
