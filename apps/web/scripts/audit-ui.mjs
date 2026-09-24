// UI audit v2: walks every nav section (closing modals between), screenshots,
// and measures layout facts: 3D canvas, horizontal overflow, blank sections.
// Run from apps/web: node scripts/audit-ui.mjs
import { chromium } from "@playwright/test";
import { mkdirSync } from "node:fs";

const BASE = process.env.AUDIT_URL ?? "https://hinaa-workspace.vercel.app";
const OUT = ".audit-out";
mkdirSync(OUT, { recursive: true });

const report = [];
const consoleErrors = [];
const pageErrors = [];

async function closeDialogs(page) {
  // Settings (and similar) render as modal <dialog>; close via Escape/Close
  await page.keyboard.press("Escape").catch(() => {});
  await page.waitForTimeout(300);
  for (const sel of [
    'dialog[open] button:has-text("Close")',
    'dialog[open] button:has-text("Done")',
    'dialog[open] [aria-label="Close"]',
  ]) {
    const el = page.locator(sel).first();
    if (await el.count()) {
      await el.click({ timeout: 1500 }).catch(() => {});
      await page.waitForTimeout(250);
    }
  }
}

async function measure(page) {
  return page.evaluate(() => {
    const canvases = [...document.querySelectorAll("canvas")].map((c) => ({
      w: c.clientWidth,
      h: c.clientHeight,
      visible: c.clientWidth > 0,
    }));
    const overflow = document.documentElement.scrollWidth - window.innerWidth;
    const main = document.querySelector("main");
    const textLen = main ? (main.textContent || "").trim().length : -1;
    return { canvases, horizontalOverflowPx: overflow, mainTextLen: textLen };
  });
}

const browser = await chromium.launch({ channel: "chrome", headless: true });

// ── Desktop ─────────────────────────────────────────────────────
{
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();
  page.on("console", (m) => { if (m.type() === "error") consoleErrors.push(m.text().slice(0, 200)); });
  page.on("pageerror", (e) => pageErrors.push(String(e).slice(0, 200)));

  await page.goto(BASE, { waitUntil: "domcontentloaded", timeout: 45000 });
  await page.waitForTimeout(4500);
  report.push(["desktop chat", await measure(page)]);
  await page.screenshot({ path: `${OUT}/desktop-chat.png` });

  for (const id of ["dashboard", "models", "reports", "settings"]) {
    const btn = page.locator(`[data-testid="sidebar-nav-${id}"]`);
    if (!(await btn.count())) { report.push([`desktop ${id}`, "NAV MISSING"]); continue; }
    await btn.click();
    await page.waitForTimeout(1800);
    report.push([`desktop ${id}`, await measure(page)]);
    await page.screenshot({ path: `${OUT}/desktop-${id}.png` });
    await closeDialogs(page);
    await page.waitForTimeout(400);
  }
  await context.close();
}

// ── Mobile ──────────────────────────────────────────────────────
{
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
    isMobile: true,
    hasTouch: true,
  });
  const page = await context.newPage();
  page.on("console", (m) => { if (m.type() === "error") consoleErrors.push(m.text().slice(0, 200)); });
  page.on("pageerror", (e) => pageErrors.push(String(e).slice(0, 200)));

  await page.goto(BASE, { waitUntil: "domcontentloaded", timeout: 45000 });
  await page.waitForTimeout(4500);
  report.push(["mobile chat top", await measure(page)]);
  await page.screenshot({ path: `${OUT}/mobile-chat-top.png` });
  await page.mouse.wheel(0, 900).catch(() => {});
  await page.waitForTimeout(800);
  report.push(["mobile chat bottom", await measure(page)]);
  await page.screenshot({ path: `${OUT}/mobile-chat-bottom.png` });
  await context.close();
}

await browser.close();

console.log("=== LAYOUT REPORT ===");
for (const [name, m] of report) {
  console.log(name, JSON.stringify(m));
}
console.log("\n=== CONSOLE ERRORS ===");
console.log(consoleErrors.length ? [...new Set(consoleErrors)].join("\n") : "(none)");
console.log("\n=== PAGE CRASHES ===");
console.log(pageErrors.length ? [...new Set(pageErrors)].join("\n") : "(none)");
