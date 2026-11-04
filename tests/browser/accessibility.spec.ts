import { exchangeSession, syntheticSignIn } from "./auth";
import { test, expect, type Page, type Locator } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const origin = "http://127.0.0.1:3116";
const alphaRole = "00000000-0000-4000-8000-000000000021";

test.beforeEach(async ({ context }) => {
  // Reuse the config's owned-runtime guard; never contact external services.
  await context.route("**/*", async (route) => {
    if (new URL(route.request().url()).origin !== origin)
      throw new Error("Accessibility browser attempted an unowned request");
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

async function signIn(page: Page) {
  await syntheticSignIn(page);
  await expect(
    page.getByRole("heading", { name: "Organization roles" }),
  ).toBeVisible();
}

async function scan(page: Page) {
  const result = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
    .analyze();
  const summarize = (items: typeof result.violations) =>
    items.map((item) => ({ id: item.id, nodes: item.nodes.length }));
  const summary = {
    test: test.info().title,
    browser: page.context().browser()?.version(),
    axe: result.testEngine.version,
    violations: summarize(result.violations),
    incomplete: summarize(result.incomplete),
  };
  // No HTML, URLs, storage, credentials, screenshots or traces retained.
  console.log("A11Y_MATRIX " + JSON.stringify(summary));
  expect.soft(summary.violations).toEqual([]);
}

async function layout(page: Page) {
  const measurement = await page.evaluate(() => {
    const root = document.documentElement;
    const controls = [
      ...document.querySelectorAll<HTMLElement>(
        "main button, main a[href], main input, main select, main textarea",
      ),
    ].filter(
      (element) =>
        element.getClientRects().length && !element.matches(":disabled"),
    );
    return {
      overflow: [...document.querySelectorAll<HTMLElement>("body *")]
        .filter((element) => {
          const box = element.getBoundingClientRect();
          return box.width > 0 && box.right > innerWidth + 1;
        })
        .map((element) => ({
          tag: element.tagName,
          region: element.closest("main") ? "main" : "shell",
          classes: element.className,
          right: Math.round(element.getBoundingClientRect().right),
        }))
        .slice(0, 12),
      viewport: innerWidth,
      documentWidth: root.scrollWidth,
      clippedControls: controls.filter((element) => {
        const box = element.getBoundingClientRect();
        return box.left < -1 || box.right > innerWidth + 1;
      }).length,
      // Geometry evidence only: axe target-size applies spacing exceptions.
      targets: controls.map((element) => {
        const box = element.getBoundingClientRect();
        return {
          tag: element.tagName,
          width: Math.round(box.width),
          height: Math.round(box.height),
        };
      }),
    };
  });
  console.log(
    "A11Y_GEOMETRY " +
      JSON.stringify({ test: test.info().title, ...measurement }),
  );
  expect
    .soft(measurement.documentWidth)
    .toBeLessThanOrEqual(measurement.viewport + 1);
  expect.soft(measurement.clippedControls).toBe(0);
}

async function reducedMotion(page: Page) {
  await page.emulateMedia({ reducedMotion: "reduce" });
  const violations = await page.evaluate(() => {
    const seconds = (value: string) =>
      value.split(",").some((part) => parseFloat(part) > 0.0001);
    return [...document.querySelectorAll("*")].flatMap((element) =>
      [null, "::before", "::after"].filter((pseudo) => {
        const style = getComputedStyle(element, pseudo);
        return (
          seconds(style.animationDuration) ||
          seconds(style.transitionDuration) ||
          style.scrollBehavior === "smooth"
        );
      }),
    ).length;
  });
  expect
    .soft(
      violations,
      "Reduced-motion styles exceeding 0.1ms or smooth scrolling",
    )
    .toBe(0);
  expect(
    await page.evaluate(
      () => matchMedia("(prefers-reduced-motion: reduce)").matches,
    ),
  ).toBe(true);
}

const screens = [
  "sign-in",
  "roles",
  "profile",
  "consent",
  "unavailable",
] as const;
for (const screen of screens) {
  for (const width of [320, 375, 1280]) {
    test(`${screen}: names, target spacing, reflow and reduced motion at ${width}px`, async ({
      page,
    }) => {
      await page.setViewportSize({ width, height: 800 });
      await page.emulateMedia({ reducedMotion: "reduce" });
      if (screen === "roles" || screen === "profile") await signIn(page);
      if (screen === "sign-in") await page.goto("/sign-in");
      if (screen === "profile") {
        await page.goto(`/roles/${alphaRole}`);
        await expect(
          page.getByRole("heading", {
            name: "Synthetic Platform Engineer",
            exact: true,
          }),
        ).toBeVisible();
      }
      if (screen === "consent") {
        // Read-only landing inspection: never accept/decline or consume smoke tokens.
        await page.goto(`/candidate/invites/${process.env.BROWSER_E2E_INVITE}`);
        await expect(
          page.getByRole("heading", { name: "Your choice and your data" }),
        ).toBeVisible();
        await expect(page.getByRole("radio")).toHaveCount(0);
        const accept = page.getByRole("button", {
          name: "I consent and want to begin",
        });
        await tabTo(page, accept);
        await page.keyboard.press("Tab");
        await expect(
          page.getByRole("button", { name: "I decline", exact: true }),
        ).toBeFocused();
        await page.keyboard.press("Shift+Tab");
        await expect(accept).toBeFocused();
      }
      if (screen === "unavailable") {
        await page.goto(
          "/candidate/invites/synthetic-invalid-accessibility-link",
        );
        await expect(
          page.getByRole("heading", {
            name: "We could not open this assessment",
          }),
        ).toBeVisible();
        const retry = page.getByRole("button", { name: "Try again" });
        await tabTo(page, retry);
        await page.keyboard.press("Enter");
        await expect(retry).toBeVisible();
      }
      await scan(page);
      await layout(page);
      await reducedMotion(page);
      await page.emulateMedia({ reducedMotion: "no-preference" });
      await reducedMotion(page); // Preference changes during use, too.
      await page.addStyleTag({
        content:
          "* { line-height: 1.5 !important; letter-spacing: .12em !important; word-spacing: .16em !important; } p { margin-bottom: 2em !important; }",
      });
      await layout(page);
    });
  }
}

test("sign-in: keyboard skip link, empty and rejected session exchange, recovery", async ({
  page,
}) => {
  await page.goto("/sign-in");
  await page.keyboard.press("Tab");
  const skip = page.getByRole("link", { name: "Skip to main content" });
  await expect(skip).toBeFocused();
  await expect(skip).toBeInViewport();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/#main-content$/);
  await expect(
    page.getByRole("heading", { name: "Sign in to Role studio" }),
  ).toBeInViewport();
  expect(await exchangeSession(page, "")).toBe(400);
  expect(await exchangeSession(page, "synthetic-invalid-token")).toBe(401);
  expect(await page.context().cookies()).toEqual([]);
  await scan(page);
  await syntheticSignIn(page);
  await expect(
    page.getByRole("heading", { name: "Organization roles" }),
  ).toBeVisible();
});

test("roles: keyboard form focus, validation, cancel and return", async ({
  page,
}) => {
  await signIn(page);
  const create = page.getByRole("button", { name: "Create role", exact: true });
  await tabTo(page, create);
  await page.keyboard.press("Enter");
  await expect(page.getByLabel("Role title")).toBeFocused();
  await tabTo(page, page.getByRole("button", { name: "Create draft role" }));
  await page.keyboard.press("Enter");
  await expect(page.getByLabel("Role title")).toBeFocused();
  await tabTo(page, page.getByRole("button", { name: "Cancel", exact: true }));
  await page.keyboard.press("Space");
  await expect(page.getByLabel("Role title")).toHaveCount(0);
  await expect.soft(create).toBeFocused();
});

test("profile: independent draft keyboard ratings, focus and narrow reflow", async ({
  page,
}) => {
  await signIn(page);
  await tabTo(
    page,
    page.getByRole("button", { name: "Create role", exact: true }),
  );
  await page.keyboard.press("Enter");
  await expect(page.getByLabel("Role title")).toBeFocused();
  await page.keyboard.insertText("Synthetic accessibility-only draft");
  await tabTo(page, page.getByLabel("Department", { exact: true }));
  await page.keyboard.insertText("Synthetic testing");
  await tabTo(page, page.getByLabel("Location", { exact: true }));
  await page.keyboard.insertText("Local only");
  await tabTo(page, page.getByLabel("Job description"));
  await page.keyboard.insertText(
    "Synthetic work involves planning, shared learning, and changing priorities.",
  );
  await tabTo(page, page.getByRole("button", { name: "Create draft role" }));
  await page.keyboard.press("Enter");
  await expect(
    page.getByRole("heading", {
      name: "Synthetic accessibility-only draft",
      exact: true,
    }),
  ).toBeVisible();
  await tabTo(
    page,
    page.getByRole("button", { name: "Extract profile from job description" }),
  );
  await page.keyboard.press("Enter");
  await expect(
    page.getByText(
      "Synthetic fixture; no scientific or human approval implied.",
    ),
  ).toBeVisible();
  const group = page
    .getByRole("group")
    .filter({ has: page.getByRole("radio") })
    .first();
  const selected = group.getByRole("radio", { checked: true });
  await tabTo(page, selected);
  const before = await selected.inputValue();
  await page.keyboard.press("ArrowRight");
  expect(
    await group.getByRole("radio", { checked: true }).inputValue(),
  ).not.toBe(before);
  await expect(group.getByRole("radio", { checked: true })).toBeFocused();
  const indicator = await group
    .getByRole("radio", { checked: true })
    .evaluate((element) => {
      return getComputedStyle(element.nextElementSibling!).boxShadow !== "none";
    });
  expect
    .soft(indicator, "Keyboard-selected radio needs a visible focus indicator")
    .toBe(true);
  await page.keyboard.press("ArrowLeft");
  expect(await group.getByRole("radio", { checked: true }).inputValue()).toBe(
    before,
  );
  await scan(page);
  await page.setViewportSize({ width: 320, height: 800 });
  await layout(page);
  await reducedMotion(page);
  // Draft remains private to this test; no seeded role/invite mutation.
});
