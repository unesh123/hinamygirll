/**
 * Mobile layout check — verifies the HINAA stage fits phone-sized viewports.
 *
 * Runs headless Chromium against the dev server, forces the lightweight
 * procedural avatar + mock provider for a deterministic layout, then asserts:
 *   - no horizontal overflow
 *   - assistant avatar pane and welcome actions remain inside the viewport
 *   - composer and status pill remain visible
 *   - zero console errors
 *
 * Usage (from apps/web): node scripts/mobile-layout-check.mjs
 * Artifacts: screenshots written to <repo root>/.runtime/mobile-<name>.png
 *
 * Note: the check forces the lightweight procedural avatar so layout stays
 * deterministic — the VRM 3D stage uses the same absolute-inset container
 * (.vrm-stage), so overflow behaviour is equivalent, but the 3D stage itself
 * is not exercised at phone sizes here.
 */

import { chromium } from "@playwright/test";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";

const REPO_ROOT = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
  "..",
);
const ARTIFACT_DIR = path.join(REPO_ROOT, ".runtime");
fs.mkdirSync(ARTIFACT_DIR, { recursive: true });

const BASE_URL = "http://127.0.0.1:5173/";
const VIEWPORTS = [
  { name: "pixel-5-393x851", width: 393, height: 851 },
  { name: "small-android-320x568", width: 320, height: 568 },
];

// Pre-flight: the check needs the Vite dev server running on :5173.
// Fail loudly instead of surfacing cryptic null-layout failures.
try {
  const probe = await fetch(BASE_URL, { method: "HEAD" });
  if (!probe.ok) throw new Error(`HTTP ${probe.status}`);
} catch {
  console.error(
    `Dev server not reachable at ${BASE_URL} — start it with \`pnpm dev\` first.`,
  );
  process.exit(2);
}

const browser = await chromium.launch({
  executablePath: process.env.HINAA_CHROMIUM_PATH || "/usr/bin/chromium",
  args: ["--no-sandbox", "--disable-dev-shm-usage", "--ignore-gpu-blocklist", "--enable-webgl", "--enable-unsafe-swiftshader"],
});
const results = [];

for (const vp of VIEWPORTS) {
  const page = await browser.newPage({
    viewport: { width: vp.width, height: vp.height },
  });
  const consoleErrors = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
  });
  page.on("pageerror", (err) => consoleErrors.push(String(err)));

  // Deterministic layout: procedural avatar + mock provider, avatar on.
  await page.addInitScript(() => {
    try {
      localStorage.setItem(
        "hinaa_settings_v1",
        JSON.stringify({
          _version: 1,
          appearance: {
            theme: "system",
            motion: "system",
            avatarVisible: true,
            avatarStyle: "procedural",
          },
          provider: { preferredMode: "mock", preferredModelByProvider: {} },
        }),
      );
    } catch {
      /* ignore */
    }
  });

  await page.goto(BASE_URL, { waitUntil: "networkidle", timeout: 20_000 }).catch(() => {});
  await page.waitForTimeout(1200);

  const layout = await page.evaluate(() => {
    const rect = (sel) => {
      const el = document.querySelector(sel);
      if (!el) return null;
      const r = el.getBoundingClientRect();
      return {
        top: Math.round(r.top),
        left: Math.round(r.left),
        right: Math.round(r.right),
        bottom: Math.round(r.bottom),
        width: Math.round(r.width),
        height: Math.round(r.height),
      };
    };
    const doc = document.documentElement;
    const avatar = rect(".avatar-pane");
    const composer = rect(".premium-composer-wrapper");
    return {
      viewport: { w: window.innerWidth, h: window.innerHeight },
      scrollWidth: doc.scrollWidth,
      overflowX: doc.scrollWidth > window.innerWidth + 1,
      avatar,
      avatarVisible: !!avatar && avatar.height > 0,
      composerVisible: !!composer && composer.bottom <= window.innerHeight + 1,
      welcomeActionVisible: !!document.querySelector('[aria-label="Research"]'),
      welcomeActions: ["Research", "Create", "Continue work", "Talk to HINAA"].map((label) => {
        const button = document.querySelector(`[aria-label="${label}"]`);
        if (!button) return false;
        const rect = button.getBoundingClientRect();
        return rect.top >= 0 && rect.bottom <= window.innerHeight + 1 && rect.left >= 0 && rect.right <= window.innerWidth + 1;
      }),
      statusPill: !!document.querySelector(".header-status"),
    };
  });

  // Invariants
  const checks = {
    noHorizontalOverflow: layout.overflowX === false,
    avatarPanePresent: !!layout.avatar,
    avatarPaneInsideViewport: !!(
      layout.avatar &&
      layout.avatar.left >= 0 &&
      layout.avatar.right <= layout.viewport.w &&
      layout.avatar.top >= 0 &&
      layout.avatar.bottom <= layout.viewport.h
    ),
    avatarPresent: layout.avatarVisible,
    welcomeActionPresent: layout.welcomeActionVisible,
    allWelcomeActionsInsideViewport: layout.welcomeActions.every(Boolean),
    composerInsideViewport: layout.composerVisible,
    statusPillPresent: layout.statusPill,
    noConsoleErrors: consoleErrors.length === 0,
  };
  const pass = Object.values(checks).every(Boolean);

  await page.screenshot({
    path: path.join(ARTIFACT_DIR, `mobile-${vp.name}.png`),
  });

  results.push({
    viewport: vp.name,
    checks,
    pass,
    consoleErrors,
    detail: {
        avatar: layout.avatar,
      scrollWidth: layout.scrollWidth,
    },
  });
  await page.close();
}

await browser.close();
console.log(JSON.stringify(results, null, 2));
process.exit(results.some((r) => !r.pass) ? 1 : 0);
