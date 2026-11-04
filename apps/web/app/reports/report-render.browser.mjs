import assert from "node:assert/strict";
import { readFile, mkdir } from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { chromium } = require(
  process.env.REPORT_PLAYWRIGHT_MODULE || "playwright",
);
const baseURL = "http://127.0.0.1:3162";
const { default: AxeBuilder } = require(
  process.env.REPORT_AXE_MODULE || "@axe-core/playwright",
);
const output = process.env.REPORT_RENDER_OUTPUT || "/tmp/iopsych-report-render";
const fixtureRoot = new URL(
  "../../../api/tests/fixtures/report_trace/",
  import.meta.url,
);
const source = JSON.parse(
  await readFile(new URL("complete.source.json", fixtureRoot), "utf8"),
);
const trace = JSON.parse(
  await readFile(new URL("complete.trace.json", fixtureRoot), "utf8"),
);
const report = {
  id: source.report_id,
  assessment_id: source.assessment_id,
  role_profile_id: source.role_profile_id,
  role_profile_version: source.role_profile_version,
  generated_at: "2026-11-04T12:00:00Z",
  usage_warning:
    "Synthetic interview preparation only. Never rank candidates or make an employment decision using this report.",
  result: source.result_json,
};
const roleId = "11111111-1111-4111-8111-111111111111";
const role = {
  id: roleId,
  organization_id: "22222222-2222-4222-8222-222222222222",
  title: "Synthetic Platform Engineer",
  department: "Engineering",
  location: "Toronto",
  status: "draft",
  created_at: "2026-11-04T12:00:00Z",
  job_description: "Synthetic service reliability role.",
};
const records = [
  {
    assessment_id: report.assessment_id,
    invitation_id: "44444444-4444-4444-8444-444444444444",
    candidate_email: "synthetic.review@example.test",
    role_profile_id: report.role_profile_id,
    role_profile_version: report.role_profile_version,
    submitted_at: report.generated_at,
    report_id: report.id,
  },
];
await mkdir(output, { recursive: true });
const browser = await chromium.launch({ headless: true });
try {
  for (const width of [1280, 375]) {
    const context = await browser.newContext({
      viewport: { width, height: 900 },
    });
    const page = await context.newPage();
    let mode = "loading";
    let releaseLoad;
    const pendingLoad = new Promise((resolve) => {
      releaseLoad = resolve;
    });
    await page.route("**/api/internal/**", async (route) => {
      const path = new URL(route.request().url()).pathname;
      if (mode === "loading" && path.endsWith(`/roles/${roleId}`))
        await pendingLoad;
      if (path.endsWith("/me"))
        return route.fulfill({
          json: {
            id: "33333333-3333-4333-8333-333333333333",
            organization_id: role.organization_id,
            email: "reviewer@example.test",
            name: "Synthetic Reviewer",
            role: "recruiter",
          },
        });
      if (mode === "error")
        return route.fulfill({
          status: 503,
          json: { detail: "Synthetic service unavailable" },
        });
      if (path.endsWith("/trace")) return route.fulfill({ json: trace });
      if (path.includes("/reports/")) return route.fulfill({ json: report });
      if (path.endsWith("/assessments"))
        return route.fulfill({ json: mode === "empty" ? [] : records });
      if (path.endsWith(`/roles/${roleId}`))
        return route.fulfill({ json: role });
      return route.fulfill({ status: 404, json: {} });
    });
    await page.goto(`${baseURL}/roles/${roleId}/reports`);
    await page
      .getByRole("status")
      .filter({ hasText: "Loading submitted assessments" })
      .waitFor();
    await page.screenshot({
      path: `${output}/loading-${width}.png`,
      fullPage: true,
    });
    mode = "ready";
    releaseLoad();
    const open = page.getByRole("button", {
      name: "View report for synthetic.review@example.test",
    });
    await open.waitFor();
    assert.deepEqual(
      (await new AxeBuilder({ page }).include("main").analyze()).violations,
      [],
    );
    await page.screenshot({
      path: `${output}/list-${width}.png`,
      fullPage: true,
    });
    await open.click();
    const heading = page.getByRole("heading", {
      name: "Report for synthetic.review@example.test",
    });
    await heading.waitFor();
    assert.deepEqual(
      (await new AxeBuilder({ page }).include("main").analyze()).violations,
      [],
    );
    assert.equal(
      await heading.evaluate((el) => el === document.activeElement),
      true,
    );
    await page.screenshot({
      path: `${output}/detail-${width}.png`,
      fullPage: true,
    });
    assert.equal(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
      true,
    );
    const evidence = page.getByRole("button", {
      name: "View evidence for Autonomy",
    });
    await evidence.click();
    const dialog = page.getByRole("dialog", { name: "Evidence: Autonomy" });
    await dialog
      .getByRole("heading", { name: "Item-level evidence" })
      .waitFor();
    assert.deepEqual(
      (await new AxeBuilder({ page }).include("dialog").analyze()).violations,
      [],
    );
    assert.equal(
      await dialog
        .getByRole("button", { name: "Close evidence" })
        .evaluate((el) => el === document.activeElement),
      true,
    );
    await page.screenshot({ path: `${output}/evidence-${width}.png` });
    await page.keyboard.press("Shift+Tab");
    assert.equal(
      await dialog.evaluate((el) => el.contains(document.activeElement)),
      true,
    );
    await page.keyboard.press("Escape");
    await dialog.waitFor({ state: "detached" });
    assert.equal(
      await evidence.evaluate((el) => el === document.activeElement),
      true,
    );
    mode = "empty";
    await page.reload();
    await page
      .getByRole("heading", { name: "No submitted assessments yet" })
      .waitFor();
    await page.screenshot({
      path: `${output}/empty-${width}.png`,
      fullPage: true,
    });
    mode = "error";
    await page.reload();
    await page.getByRole("heading", { name: "Report unavailable" }).waitFor();
    await page.screenshot({
      path: `${output}/error-${width}.png`,
      fullPage: true,
    });
    mode = "ready";
    await page.getByRole("button", { name: "Try again" }).click();
    await open.waitFor();
    await context.close();
  }
  console.log(
    `Report desktop/mobile renders and keyboard checks passed: ${output}`,
  );
} finally {
  await browser.close();
}
