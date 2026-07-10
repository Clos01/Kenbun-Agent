#!/usr/bin/env node
// Hydration smoke test for the Kenbun dashboard.
//
// Catches the failure mode that HTTP/curl checks cannot: a page that serves
// 200 with valid-looking SSR HTML but never hydrates (dead UI, no console
// errors, no data). Cause seen 2026-07-09: wrong IP in allowedDevOrigins made
// Turbopack's dev runtime reject the real origin — every page went silently
// non-interactive. This script asserts, per route, that the CLIENT actually
// runs: it must issue /api_proxy requests, and none may return >= 400.
//
// Usage:  cd dashboard/scripts && npm i --silent && node smoke.mjs [baseUrl]
// Default baseUrl: http://100.92.127.1:3000 (lg2025 dev dashboard)
// Exit code 0 = all routes pass; 1 = at least one failure.

import { chromium } from "playwright-core";
import { existsSync, readdirSync } from "node:fs";
import { homedir, platform } from "node:os";
import { join } from "node:path";

const BASE = process.argv[2] || "http://100.92.127.1:3000";
const ROUTES = ["/observatory", "/board", "/supervisor", "/chat"];
const SETTLE_MS = 9000; // dev-mode first compile + data polling warm-up

function findBrowser() {
  if (process.env.KENBUN_SMOKE_BROWSER) return process.env.KENBUN_SMOKE_BROWSER;
  const cache = join(homedir(), platform() === "darwin" ? "Library/Caches/ms-playwright" : ".cache/ms-playwright");
  if (existsSync(cache)) {
    const dirs = readdirSync(cache).filter((d) => d.startsWith("chromium")).sort().reverse();
    for (const d of dirs) {
      const candidates = platform() === "darwin"
        ? [
            join(cache, d, "chrome-headless-shell-mac-arm64/chrome-headless-shell"),
            join(cache, d, "chrome-headless-shell-mac-x64/chrome-headless-shell"),
            join(cache, d, "chrome-mac/Chromium.app/Contents/MacOS/Chromium"),
          ]
        : [
            join(cache, d, "chrome-headless-shell-linux64/chrome-headless-shell"),
            join(cache, d, "chrome-linux/chrome"),
          ];
      for (const c of candidates) if (existsSync(c)) return c;
    }
  }
  const system = platform() === "darwin"
    ? ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"]
    : ["/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser"];
  for (const c of system) if (existsSync(c)) return c;
  throw new Error(
    "No Chromium found. Set KENBUN_SMOKE_BROWSER=/path/to/chrome, or run: npx playwright-core install chromium"
  );
}

const browser = await chromium.launch({ executablePath: findBrowser(), headless: true });
let failed = false;

for (const route of ROUTES) {
  const page = await browser.newPage({ viewport: { width: 1500, height: 950 } });
  const apiCalls = new Set();
  const apiErrors = new Set();
  const pageErrors = [];
  page.on("request", (r) => {
    if (r.url().includes("/api_proxy/")) apiCalls.add(r.url().split("/api_proxy/")[1].split("?")[0]);
  });
  page.on("response", (r) => {
    if (r.url().includes("/api_proxy/") && r.status() >= 400)
      apiErrors.add(`${r.status()} ${r.url().split("/api_proxy/")[1].split("?")[0]}`);
  });
  page.on("pageerror", (e) => pageErrors.push(e.message.slice(0, 120)));

  let navStatus = "no-response";
  try {
    const res = await page.goto(BASE + route, { waitUntil: "networkidle", timeout: 120000 });
    navStatus = res ? String(res.status()) : "no-response";
  } catch (e) {
    navStatus = "nav-error: " + e.message.slice(0, 60);
  }
  await page.waitForTimeout(SETTLE_MS);

  const problems = [];
  if (navStatus !== "200") problems.push(`HTTP ${navStatus}`);
  if (apiCalls.size === 0) problems.push("NO api_proxy calls — page did not hydrate");
  if (apiErrors.size > 0) problems.push(`API errors: ${[...apiErrors].join(", ")}`);
  if (pageErrors.length > 0) problems.push(`JS errors: ${pageErrors[0]}`);

  if (problems.length) {
    failed = true;
    console.log(`✗ ${route}  ${problems.join(" | ")}`);
  } else {
    console.log(`✓ ${route}  hydrated, ${apiCalls.size} distinct API calls, no errors`);
  }
  await page.close();
}

await browser.close();
if (failed) {
  console.log("\nSMOKE FAILED — the dashboard is serving pages that do not work in a browser.");
  process.exit(1);
}
console.log("\nSMOKE PASSED");
