import { test, expect, type Page, type Locator } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { readFileSync } from "node:fs";

const alphaRole = "00000000-0000-4000-8000-000000000021";
const beaconRole = "00000000-0000-4000-8000-000000000022";
const foreignAssessment = "00000000-0000-4000-8000-000000000097";
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
      throw new Error("Privacy history attempted an unowned request");
    await route.continue();
  });
});

async function signIn(page: Page, identity: "ADMIN" | "MANAGER") {
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
  throw new Error("Action was not reachable within 100 Tab presses");
}

async function scan(page: Page) {
  const result = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
    .analyze();
  const summarize = (items: typeof result.violations) =>
    items.map(({ id, nodes }) => ({ id, nodes: nodes.length }));
  console.log(
    "PRIVACY_HISTORY_AXE " +
      JSON.stringify({
        violations: summarize(result.violations),
        incomplete: summarize(result.incomplete),
      }),
  );
  expect.soft(summarize(result.violations)).toEqual([]);
}

test("selected assessment traverses real linked history, retains pagination scope and documents deletion lineage", async ({
  page,
}) => {
  test.setTimeout(120_000);
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
  await page.goto(`/roles/${alphaRole}/reports`);
  await page
    .getByRole("button", {
      name: "Generate report for privacy@example.invalid",
    })
    .click();
  await expect(
    page.getByRole("heading", { name: "Report for privacy@example.invalid" }),
  ).toBeVisible();
  const evidence = page.getByRole("button", {
    name: "View evidence for Autonomy",
  });
  await tabTo(page, evidence);
  await page.keyboard.press("Enter");
  await expect(
    page.getByRole("dialog", { name: "Evidence: Autonomy" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Close evidence" }),
  ).toBeFocused();
  await scan(page);
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(evidence).toBeFocused();
  await page.goto("/privacy");
  await page.getByLabel("Reference type").selectOption("role_id");
  await page.getByLabel("Reference ID", { exact: true }).fill(alphaRole);
  await page.getByRole("button", { name: "Find assessments" }).click();
  const select = page.getByRole("button", { name: /^Select assessment / });
  await expect(select).toHaveCount(1);
  await tabTo(page, select);
  await page.keyboard.press("Enter");
  await expect(select).toBeFocused();
  await expect(select).toHaveAttribute("aria-pressed", "true");
  const assessmentId = await page
    .getByLabel("Assessment ID", { exact: true })
    .inputValue();
  const exported = await page.request.post(
    `/api/internal/candidates/${assessmentId}/export`,
    { headers: { Origin: "http://127.0.0.1:3116" } },
  );
  expect(exported.status()).toBe(200);
  const lineage = await exported.json();
  expect(lineage.reports).toHaveLength(1);
  const history = page.getByRole("region", { name: "Immutable audit history" });
  await page.getByRole("button", { name: "Look up audit history" }).click();
  for (const event of [
    "candidate_invite.accessed",
    "candidate_consent.recorded",
    "assessment.submitted",
    "alignment_report.generation_requested",
  ]) {
    await expect(
      history.getByText(event, { exact: true }).first(),
    ).toBeVisible();
  }
  for (const [type, id] of [
    ["assessment_invite", lineage.invitation.id],
    ["assessment", assessmentId],
    ["alignment_report", lineage.reports[0].id],
  ]) {
    await expect(
      history.getByText(`${type} · ${id}`, { exact: true }).first(),
    ).toBeVisible();
  }
  await scan(page);
  for (let index = 0; index < 51; index++) {
    const response = await page.request.post(
      `/api/internal/candidates/${assessmentId}/export`,
      { headers: { Origin: "http://127.0.0.1:3116" } },
    );
    expect(response.status()).toBe(200);
    await response.dispose();
  }
  await page.getByRole("button", { name: "Look up audit history" }).click();
  await expect(history.getByRole("listitem")).toHaveCount(50);
  const more = history.getByRole("button", { name: "Load more audit history" });
  await tabTo(page, more);
  const nextResponse = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      url.pathname === "/api/internal/privacy/audit-events" &&
      url.searchParams.has("before")
    );
  });
  await page.keyboard.press("Enter");
  const next = await nextResponse;
  expect(next.status()).toBe(200);
  expect(new URL(next.url()).searchParams.get("assessment_id")).toBe(
    assessmentId,
  );
  expect(new URL(next.url()).searchParams.has("entity_id")).toBe(false);
  await expect(more).toHaveCount(0);
  await expect(
    history.getByText("candidate_consent.recorded", { exact: true }),
  ).toBeVisible();
  await expect(page.getByLabel("Assessment ID", { exact: true })).toHaveValue(
    assessmentId,
  );
  await expect(select).toHaveAttribute("aria-pressed", "true");
  const related = await page.request.get(
    `/api/internal/privacy/audit-events?assessment_id=${assessmentId}&limit=200`,
  );
  const events = await related.json();
  expect(new Set(events.map((event: { id: string }) => event.id)).size).toBe(
    events.length,
  );
  await expect(history.getByRole("listitem")).toHaveCount(events.length);
  const foreign = await page.request.get(
    `/api/internal/privacy/assessments?role_id=${beaconRole}`,
  );
  expect(foreign.status()).toBe(200);
  expect(await foreign.json()).toEqual({
    schema_version: "1.0",
    items: [],
    next_cursor: null,
  });
  const foreignHistory = await page.request.get(
    `/api/internal/privacy/audit-events?assessment_id=${foreignAssessment}`,
  );
  expect(foreignHistory.status()).toBe(404);
  const missing = await page.request.get(
    "/api/internal/privacy/audit-events?assessment_id=00000000-0000-4000-8000-000000000000",
  );
  expect(missing.status()).toBe(404);
  await page.getByRole("button", { name: "Prepare anonymization" }).click();
  await page.getByRole("button", { name: "Confirm anonymization" }).click();
  await expect(
    page.getByText(
      `Assessment ${assessmentId} was anonymized. Derived reports removed: 1.`,
    ),
  ).toBeVisible();
  const after = await page.request.get(
    `/api/internal/privacy/audit-events?assessment_id=${assessmentId}&limit=200`,
  );
  const afterEvents = await after.json();
  expect(
    afterEvents.some(
      (event: { event_type: string }) =>
        event.event_type === "candidate_data.deletion_requested",
    ),
  ).toBe(true);
  expect(
    afterEvents.some(
      (event: { entity_type: string }) =>
        event.entity_type === "alignment_report",
    ),
  ).toBe(false);
  const tombstones = await page.request.get(
    `/api/internal/privacy/audit-events?entity_id=${lineage.reports[0].id}`,
  );
  expect(
    (await tombstones.json()).some(
      (event: { event_type: string }) =>
        event.event_type === "alignment_report.generation_requested",
    ),
  ).toBe(true);
  await signIn(page, "MANAGER");
  const beaconSubmissions = await page.request.get(
    `/api/internal/roles/${beaconRole}/assessments`,
  );
  expect(beaconSubmissions.status()).toBe(200);
  expect(
    (await beaconSubmissions.json()).some(
      (item: { assessment_id: string }) =>
        item.assessment_id === foreignAssessment,
    ),
  ).toBe(true);
  await page.goto("/privacy");
  await expect(
    page.getByRole("heading", { name: "Administrator access required" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Look up audit history" }),
  ).toHaveCount(0);
  for (const query of [
    `assessment_id=${assessmentId}`,
    `assessment_id=${foreignAssessment}`,
    `entity_id=${lineage.reports[0].id}`,
    "limit=50",
  ]) {
    expect(
      (
        await page.request.get(`/api/internal/privacy/audit-events?${query}`)
      ).status(),
    ).toBe(403);
  }
  await scan(page);
});
