import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { once } from "node:events";
import { createServer } from "node:http";
import { createRequire } from "node:module";
import { fileURLToPath, pathToFileURL } from "node:url";

const require = createRequire(import.meta.url);
const playwrightPath = process.env.PLAYWRIGHT_MODULE_PATH;
const { chromium } = await import(
  playwrightPath
    ? pathToFileURL(playwrightPath).href
    : pathToFileURL(require.resolve("playwright")).href
);
const development = process.argv.includes("--development");
const origin = "http://localhost:3130";
const name = development
  ? "iopsych_internal_token"
  : "__Host-iopsych_internal_token";
const token = "synthetic-signout-regression";
const probe = createServer();
probe.listen(3130);
await once(probe, "listening");
await new Promise((resolve) => probe.close(resolve));
let upstreamRequests = 0;
const upstream = createServer((request, response) => {
  upstreamRequests += 1;
  const valid = request.headers.authorization === `Bearer ${token}`;
  response.writeHead(valid ? 200 : 401, { "Content-Type": "application/json" });
  response.end(
    JSON.stringify(
      request.url === "/v1/auth/me" ? { id: "synthetic-user" } : [],
    ),
  );
});
upstream.listen(8130, "127.0.0.1");
await once(upstream, "listening");
const server = spawn(
  process.execPath,
  [
    require.resolve("next/dist/bin/next"),
    development ? "dev" : "start",
    "--hostname",
    "127.0.0.1",
    "--port",
    "3130",
  ],
  {
    cwd: fileURLToPath(new URL("../../../", import.meta.url)),
    env: {
      ...process.env,
      NODE_ENV: development ? "development" : "production",
      API_BASE_URL: "http://127.0.0.1:8130",
      NEXT_TELEMETRY_DISABLED: "1",
    },
    stdio: "ignore",
  },
);
let browser;
try {
  let ready = false;
  for (let attempt = 0; attempt < 120; attempt += 1) {
    if (server.exitCode !== null)
      throw new Error(`Next exited ${server.exitCode}`);
    try {
      if ((await fetch(`${origin}/api/health`)).ok) {
        ready = true;
        break;
      }
    } catch {}
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  assert.ok(ready, "Next server became ready");
  browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ serviceWorkers: "block" });
  await context.route("**/*", (route) =>
    new URL(route.request().url()).origin === origin
      ? route.continue()
      : route.abort(),
  );
  const page = await context.newPage();
  await page.goto(`${origin}/api/health`);
  const request = (path, options) =>
    page.evaluate(
      async ({ path, options }) => {
        const response = await fetch(path, options);
        return { status: response.status, body: await response.text() };
      },
      { path, options },
    );
  assert.equal((await request("/api/internal/roles")).status, 401);
  assert.equal(
    (
      await request("/api/session", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token }),
      })
    ).status,
    200,
  );
  const cookie = (await context.cookies()).find((entry) => entry.name === name);
  assert.ok(cookie, "browser accepted the session cookie");
  assert.equal(cookie.secure, !development);
  assert.equal(cookie.httpOnly, true);
  assert.equal(cookie.sameSite, "Strict");
  assert.equal(cookie.path, "/");
  assert.equal(cookie.domain, "localhost");
  assert.equal((await request("/api/internal/roles")).status, 200);
  const beforeSignout = upstreamRequests;
  const responsePromise = page.waitForResponse(
    (response) =>
      response.url() === `${origin}/api/session` &&
      response.request().method() === "DELETE",
  );
  assert.deepEqual(await request("/api/session", { method: "DELETE" }), {
    status: 204,
    body: "",
  });
  const expiration = (await (await responsePromise).allHeaders())["set-cookie"];
  assert.ok(expiration.includes("Max-Age=0"));
  assert.ok(expiration.includes("Path=/"));
  assert.equal(expiration.includes("Secure"), !development);
  assert.equal(expiration.includes("Domain="), false);
  assert.equal(
    (await context.cookies()).some((entry) => entry.name === name),
    false,
  );
  assert.equal((await request("/api/internal/roles")).status, 401);
  assert.equal(upstreamRequests, beforeSignout);
  assert.equal(
    (await request("/api/session", { method: "DELETE" })).status,
    204,
  );
  console.log(
    `${development ? "development" : "production"}: browser POST 200, roles 200, DELETE 204, cookie absent, roles 401; no upstream request after sign-out`,
  );
} finally {
  await browser?.close();
  if (server.exitCode === null) {
    const exited = once(server, "exit");
    server.kill("SIGTERM");
    await exited;
  }
  await new Promise((resolve) => upstream.close(resolve));
}
