import { exchangeSession, syntheticSignIn } from "./auth";
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
    if (url.origin !== "http://127.0.0.1:3116") {
      throw new Error("Browser attempted a nonlocal or unowned request");
    }
    await route.continue();
  });
});

async function accessible(page: import("@playwright/test").Page) {
  const result = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
    .analyze();
  // Never retain DOM, answer payloads, bearer URLs or raw HTML.
  console.log(
    "AXE_SUMMARY " +
      JSON.stringify({
        test: test.info().title,
        engine: result.testEngine.version,
        violations: result.violations.map((v) => ({
          id: v.id,
          impact: v.impact,
          nodes: v.nodes.length,
        })),
        incomplete: result.incomplete.map((v) => ({
          id: v.id,
          nodes: v.nodes.length,
        })),
      }),
  );
  expect
    .soft(
      result.violations.map((v) => ({
        id: v.id,
        impact: v.impact,
        targets: v.nodes.map((n) => n.target),
      })),
    )
    .toEqual([]);
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
  await expect(page.getByLabel("Internal access token")).toHaveCount(0);
  expect(await exchangeSession(page, "synthetic-invalid-token")).toBe(401);
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

async function signIn(
  page: import("@playwright/test").Page,
  identity = "RECRUITER",
) {
  await syntheticSignIn(page, identity);
  await expect(page).toHaveURL(/\/roles$/);
  await expect(
    page.getByRole("heading", { name: "Organization roles" }),
  ).toBeVisible();
  const cookies = await page.context().cookies();
  expect(
    cookies.some((c) => c.httpOnly && c.secure && c.sameSite === "Strict"),
  ).toBe(true);
}

const alphaRole = "00000000-0000-4000-8000-000000000021";
const beaconRole = "00000000-0000-4000-8000-000000000022";

test("recruiter creates and extracts a synthetic draft with immutable revision", async ({
  page,
}) => {
  await signIn(page);
  await expect(
    page.getByRole("heading", { name: "Synthetic Platform Engineer" }),
  ).toBeVisible();
  await expect(page.getByText("Synthetic Program Lead")).toHaveCount(0);
  await accessible(page);
  await page.getByRole("button", { name: "Create role", exact: true }).click();
  await expect(page.getByLabel("Role title")).toBeFocused();
  await accessible(page);
  await page.getByLabel("Role title").fill("Synthetic browser draft");
  await page
    .getByLabel("Department", { exact: true })
    .fill("Synthetic testing");
  await page.getByLabel("Location", { exact: true }).fill("Local only");
  await page
    .getByLabel("Job description")
    .fill(
      "Synthetic work involves planning, shared learning, and changing priorities.",
    );
  await page.getByRole("button", { name: "Create draft role" }).click();
  await expect(
    page.getByRole("heading", { name: "Synthetic browser draft", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Extract profile from job description" })
    .click();
  await expect(
    page.getByText(
      "Synthetic fixture; no scientific or human approval implied.",
    ),
  ).toBeVisible();
  await accessible(page);
  await expect(
    page.getByRole("button", { name: "Approve", exact: false }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "Save new version" }).click();
  await expect(page.getByRole("button", { name: /Version 2/ })).toBeVisible();
  await expect(page.getByRole("button", { name: /Version 1/ })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("button", { name: /Version 2/ })).toBeVisible();
});

test("separate manager tenant cannot read or mutate recruiter resources", async ({
  page,
}) => {
  await signIn(page, "MANAGER");
  await expect(
    page.getByRole("heading", { name: "Synthetic Program Lead" }),
  ).toBeVisible();
  await expect(page.getByText("Synthetic Platform Engineer")).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Create role", exact: true }),
  ).toHaveCount(0);
  await accessible(page);
  const statuses = await page.evaluate(async (id) => {
    return Promise.all(
      [
        fetch(`/api/internal/roles/${id}`),
        fetch(`/api/internal/roles/${id}/profiles`),
        fetch(`/api/internal/roles/${id}/assessments`),
        fetch(`/api/internal/roles/${id}/extract-profile`, { method: "POST" }),
      ].map(async (request) => (await request).status),
    );
  }, alphaRole);
  expect(statuses.slice(0, 3)).toEqual([404, 404, 404]);
  expect([403, 404]).toContain(statuses[3]);
  await page.goto(`/roles/${alphaRole}`);
  await expect(
    page.getByRole("heading", { name: "Role profile unavailable" }),
  ).toBeVisible();
  await accessible(page);
  await page.goto(`/roles/${beaconRole}`);
  await expect(
    page.getByRole("heading", { name: "Synthetic Program Lead", exact: true }),
  ).toBeVisible();
  await accessible(page);
  await page.goto("/privacy");
  await expect(
    page.getByRole("heading", { name: "Administrator access required" }),
  ).toBeVisible();
  await accessible(page);
  expect(
    await page.evaluate(
      async () => (await fetch("/api/internal/privacy/status")).status,
    ),
  ).toBe(403);
  expect(
    await page.evaluate(
      async () => (await fetch("/api/session", { method: "DELETE" })).status,
    ),
  ).toBe(204);
  expect(
    await page.evaluate(
      async () => (await fetch("/api/internal/roles")).status,
    ),
  ).toBe(401);
});

for (const mode of ["COMPLETE", "DENIED", "QUOTA", "CLEAR"]) {
  test(`candidate completes with ${mode.toLowerCase()} device storage`, async ({
    page,
  }) => {
    if (mode === "DENIED") {
      await page.addInitScript(() => {
        Object.defineProperty(window, "localStorage", {
          get() {
            throw new DOMException("Synthetic denial", "SecurityError");
          },
        });
      });
    } else if (mode === "QUOTA") {
      await page.addInitScript(() => {
        Storage.prototype.setItem = () => {
          throw new DOMException("Synthetic quota", "QuotaExceededError");
        };
      });
    }
    await page.goto(`/candidate/invites/${process.env[`BROWSER_E2E_${mode}`]}`);
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
      if (mode === "DENIED" || mode === "QUOTA")
        await expect(
          page.getByText(
            "Not saved on this device. Keep this page open to finish.",
          ),
        ).toBeVisible();
      if (block === 1) {
        await accessible(page);
        if (mode === "COMPLETE") {
          await expect(
            page.getByText("Saved on this device", { exact: true }),
          ).toBeVisible();
          await page.reload();
          await page.getByRole("button", { name: "Previous block" }).click();
          await expect(page.getByRole("radio", { checked: true })).toHaveCount(
            2,
          );
        }
      }
      await page
        .getByRole("button", {
          name:
            block === definition.blocks.length ? "Review answers" : "Continue",
          exact: true,
        })
        .click();
    }
    await expect(
      page.getByRole("heading", { name: "Review your responses" }),
    ).toBeVisible();
    await accessible(page);
    if (mode === "CLEAR") {
      await page.getByRole("button", { name: "Clear device data" }).click();
      await expect(
        page.getByRole("heading", { name: "Assessment paused" }),
      ).toBeVisible();
      expect(
        await page.evaluate(() =>
          Object.keys(localStorage).filter((key) =>
            key.startsWith("iopsych.candidate."),
          ),
        ),
      ).toEqual([]);
      await page.getByRole("button", { name: "Continue assessment" }).click();
      for (let block = 1; block <= definition.blocks.length; block++) {
        await expect(
          page.getByText(`Block ${block} of ${definition.blocks.length}`, {
            exact: true,
          }),
        ).toBeVisible();
        await expect(page.getByRole("radio", { checked: true })).toHaveCount(0);
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
              block === definition.blocks.length
                ? "Review answers"
                : "Continue",
            exact: true,
          })
          .click();
      }
      await expect(
        page.getByRole("heading", { name: "Review your responses" }),
      ).toBeVisible();
    }
    const submission = page.waitForResponse(
      (r) => r.url().endsWith("/submit") && r.request().method() === "POST",
    );
    await page.getByRole("button", { name: "Submit my responses" }).click();
    expect((await submission).status()).toBe(201);
    await expect(
      page.getByRole("heading", { name: "Your responses are complete" }),
    ).toBeVisible();
    await accessible(page);
    if (mode === "COMPLETE") {
      const shapes = await page.evaluate(() =>
        Object.keys(localStorage)
          .filter((k) => k.startsWith("iopsych.candidate."))
          .map((k) => ({
            kind: k.split(".").at(-1),
            keys: Object.keys(JSON.parse(localStorage.getItem(k)!)).sort(),
          })),
      );
      expect(shapes).toEqual([
        { kind: "completion", keys: ["assessment_id", "submitted_at"] },
      ]);
    }
    await page.reload();
    await expect(
      page.getByRole("heading", { name: "Your responses are complete" }),
    ).toBeVisible();
    await expect(page.getByRole("radio")).toHaveCount(0);
  });
}

test("submitted responses generate a saved report and native evidence dialog", async ({
  page,
}) => {
  await signIn(page);
  await page.goto(`/roles/${alphaRole}/reports`);
  const generate = page.getByRole("button", {
    name: "Generate report for complete@example.invalid",
  });
  await expect(generate).toBeVisible();
  await accessible(page);
  await generate.click();
  await expect(
    page.getByRole("heading", { name: "Report for complete@example.invalid" }),
  ).toBeVisible();
  await accessible(page);
  const trigger = page.getByRole("button", {
    name: "View evidence for Autonomy",
  });
  await trigger.click();
  await expect(
    page.getByRole("dialog", { name: "Evidence: Autonomy" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Close evidence" }),
  ).toBeFocused();
  await accessible(page);
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(trigger).toBeFocused();
  await page.getByRole("link", { name: "Open saved report link" }).click();
  await expect(
    page.getByRole("heading", { name: "Construct comparison report" }),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Construct comparison report" }),
  ).toBeVisible();
  for (const width of [320, 375, 1280]) {
    await page.setViewportSize({ width, height: 800 });
    const historicalTrigger = page.getByRole("button", {
      name: "View evidence for Autonomy",
    });
    await historicalTrigger.focus();
    await page.keyboard.press("Enter");
    const dialog = page.getByRole("dialog", { name: "Evidence: Autonomy" });
    const evidence = dialog.getByRole("region", {
      name: "Item-level evidence",
    });
    await expect(evidence.getByRole("listitem")).toHaveCount(4);
    const historicalItems = definition.blocks.flatMap(
      (block: { items: { construct_key: string; statement: string }[] }) =>
        block.items.filter((item) => item.construct_key === "autonomy"),
    );
    for (let index = 0; index < historicalItems.length; index++) {
      await expect(evidence.getByRole("listitem").nth(index)).toContainText(
        historicalItems[index].statement,
      );
    }
    await expect(evidence).toContainText("Inclusive rating band:");
    await expect(evidence).toContainText("Completeness:");
    await expect(
      dialog.getByRole("button", { name: "Close evidence" }),
    ).toBeFocused();
    await accessible(page);
    const geometry = await dialog.evaluate((element) => ({
      width: element.clientWidth,
      content: element.scrollWidth,
      right: element.getBoundingClientRect().right,
    }));
    expect.soft(geometry.content).toBeLessThanOrEqual(geometry.width + 1);
    expect.soft(geometry.right).toBeLessThanOrEqual(width + 1);
    for (let step = 0; step < 4; step++) {
      await page.keyboard.press("Tab");
      const focus = await dialog.evaluate((element) => ({
        tag: document.activeElement?.tagName,
        inDialog: element.contains(document.activeElement),
        browserBoundary: document.activeElement === document.body,
      }));
      console.log(
        "HISTORICAL_FOCUS " + JSON.stringify({ width, step, ...focus }),
      );
      expect.soft(focus.inDialog || focus.browserBoundary).toBe(true);
    }
    await page.keyboard.press("Escape");
    await expect(dialog).toHaveCount(0);
    await expect(historicalTrigger).toBeFocused();
  }
});

test("synthetic administrator exports and anonymizes only the disposable candidate", async ({
  page,
}) => {
  await signIn(page, "ADMIN");
  const assessmentId = await page.evaluate(async (role) => {
    const response = await fetch(`/api/internal/roles/${role}/assessments`);
    if (!response.ok) throw new Error("Synthetic source lookup failed");
    const sources = await response.json();
    return sources.find(
      (source: { candidate_email: string }) =>
        source.candidate_email === "quota@example.invalid",
    )?.assessment_id;
  }, alphaRole);
  expect(typeof assessmentId).toBe("string");
  await page.goto("/privacy");
  await expect(
    page.getByRole("heading", { name: "Candidate privacy", exact: true }),
  ).toBeVisible();
  await accessible(page);
  await page.getByLabel("Assessment ID").fill(assessmentId);
  await page.getByRole("button", { name: "Create JSON export" }).click();
  await expect(
    page.getByRole("link", { name: "Download JSON export" }),
  ).toBeVisible();
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("link", { name: "Download JSON export" }).click();
  const download = await downloadPromise;
  expect(await download.failure()).toBeNull();
  // The export contains synthetic answers: remove it without attaching/printing it.
  await download.delete();
  await page.getByRole("button", { name: "Prepare anonymization" }).click();
  await expect(
    page.getByRole("button", { name: "Confirm anonymization" }),
  ).toBeVisible();
  await accessible(page);
  await page.getByRole("button", { name: "Confirm anonymization" }).click();
  await expect(
    page.getByText(`Assessment ${assessmentId} was anonymized.`, {
      exact: false,
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Download JSON export" }),
  ).toHaveCount(0);
  const status = await page.evaluate(
    async (id) =>
      (await fetch(`/api/internal/candidates/${id}/export`, { method: "POST" }))
        .status,
    assessmentId,
  );
  expect(status).toBe(410);
});
