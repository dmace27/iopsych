import { defineConfig } from "@playwright/test";

if (
  process.env.BROWSER_E2E_OWNED !== "1" ||
  [
    "INVITE",
    "COMPLETE",
    "DENIED",
    "QUOTA",
    "RECRUITER",
    "MANAGER",
    "ADMIN",
  ].some((key) => !process.env[`BROWSER_E2E_${key}`])
) {
  throw new Error(
    "Run scripts/browser-e2e.sh; standalone tests must not target existing services.",
  );
}
export default defineConfig({
  testDir: ".",
  testMatch: "*.spec.ts",
  workers: 1,
  retries: 0,
  forbidOnly: true,
  reporter: [["list"]],
  use: {
    baseURL: "http://127.0.0.1:3116",
    browserName: "chromium",
    serviceWorkers: "block",
    // Bearer invite URLs must not become durable screenshots/traces/videos.
    trace: "off",
    screenshot: "off",
    video: "off",
  },
});
