import { chromium } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const OUT = path.resolve("scratch/ui-smoke2");
fs.mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch({
  args: [
    "--use-fake-ui-for-media-stream",
    "--use-fake-device-for-media-stream",
    "--autoplay-policy=no-user-gesture-required",
  ],
});
const ctx = await browser.newContext({
  viewport: { width: 1440, height: 900 },
  permissions: ["microphone"],
});
const page = await ctx.newPage();

const errors = [];
const consoleErrors = [];
page.on("console", (m) => {
  if (m.type() === "error") consoleErrors.push(m.text());
});
page.on("pageerror", (e) => errors.push(`pageerror: ${e.message}\n${(e.stack || "").split("\n").slice(0, 6).join("\n")}`));
page.on("requestfailed", (r) => {
  errors.push(`requestfailed: ${r.url()} :: ${r.failure()?.errorText}`);
});
page.on("response", (r) => {
  if (r.status() >= 400) errors.push(`http ${r.status()}: ${r.url()}`);
});

await page.goto("http://127.0.0.1:5173/", { waitUntil: "domcontentloaded", timeout: 60000 });
await page.waitForTimeout(3500);

const dump = async (name) => {
  await page.screenshot({ path: path.join(OUT, `${name}.png`), fullPage: false });
  const txt = (await page.evaluate(() => document.body.innerText)).slice(0, 300);
  console.log(`\n=== ${name} ===\n${txt}\n`);
};

await dump("01-work");

// Navigate to Talk by clicking on Live Voice header
const sections = ["talk", "images", "library", "projects"];
for (const s of sections) {
  try {
    // Find the section nav item by aria-label
    const candidates = await page.locator(`[aria-label]`).all();
    let clicked = false;
    for (const c of candidates) {
      const lbl = (await c.getAttribute("aria-label")) || "";
      const map = {
        talk: /live voice|voice|avatar|companion|talk/i,
        images: /image/i,
        library: /library/i,
        projects: /project/i,
      };
      if (map[s] && map[s].test(lbl)) {
        await c.click({ timeout: 2000 });
        clicked = true;
        break;
      }
    }
    if (!clicked) {
      // Fallback: find button by text
      const btn = page.locator(`button:has-text("${s}")`).first();
      if (await btn.count()) await btn.click({ timeout: 2000 });
    }
  } catch (e) {
    console.log(`nav ${s} click failed: ${e.message}`);
  }
  await page.waitForTimeout(3500);
  await dump(`0${sections.indexOf(s) + 2}-${s}`);
}

// Now try starting live voice from Talk view
console.log("\n=== Live voice test ===");
await page.evaluate(() => {
  const btns = [...document.querySelectorAll("button")];
  const start = btns.find((b) => /start voice|start live|microphone|mic|🎤/i.test(b.textContent || b.getAttribute("aria-label") || ""));
  start?.click();
});
await page.waitForTimeout(5000);
await dump("06-voice-on");

console.log("\n=== ERRORS ===");
console.log("pageerrors:", errors.length);
console.log("consoleerrors:", consoleErrors.length);
fs.writeFileSync(path.join(OUT, "errors.txt"), errors.join("\n---\n"));
fs.writeFileSync(path.join(OUT, "console.txt"), consoleErrors.join("\n"));

await browser.close();