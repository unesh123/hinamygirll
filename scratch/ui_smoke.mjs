import { chromium } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const OUT = path.resolve("scratch/ui-smoke");
fs.mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch({ args: ["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"] });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, permissions: ["microphone"] });
const page = await ctx.newPage();

const errors = [];
const logs = [];
page.on("console", (m) => {
  const t = m.type();
  logs.push(`[${t}] ${m.text()}`);
  if (t === "error") errors.push(`console: ${m.text()}`);
});
page.on("pageerror", (e) => errors.push(`pageerror: ${e.message}\n${(e.stack || "").split("\n").slice(0, 6).join("\n")}`));
page.on("requestfailed", (r) => errors.push(`requestfailed: ${r.url()} :: ${r.failure()?.errorText}`));
page.on("response", (r) => {
  if (r.status() >= 400) errors.push(`http ${r.status()}: ${r.url()}`);
});

await page.goto("http://127.0.0.1:5173/", { waitUntil: "networkidle", timeout: 60000 });
await page.waitForTimeout(3000);

const dump = async (name) => {
  const info = await page.evaluate(() => {
    const root = document.getElementById("root");
    return {
      rootChildren: root ? root.children.length : -1,
      bodyTextLen: (document.body.innerText || "").length,
      firstText: (document.body.innerText || "").slice(0, 400),
      hasAppShell: !!document.querySelector(".hinaa-shell"),
    };
  });
  await page.screenshot({ path: path.join(OUT, `${name}.png`), fullPage: false });
  console.log(`=== ${name} ===`, JSON.stringify(info, null, 2));
};

await dump("01-work");

// Navigate through nav sections
const sections = ["talk", "images", "library", "projects"];
for (const s of sections) {
  try {
    const btn = page.locator(`[data-nav="${s}"]`).first();
    if (await btn.count()) {
      await btn.click({ timeout: 3000 });
    } else {
      await page.evaluate((sec) => {
        const el = [...document.querySelectorAll("button,[role=button],a")].find((e) => (e.textContent || "").toLowerCase().includes(sec));
        el?.click();
      }, s);
    }
  } catch (e) {
    console.log(`nav ${s} click failed: ${e.message}`);
  }
  await page.waitForTimeout(2500);
  await dump(`0${sections.indexOf(s) + 2}-${s}`);
}

console.log("\n=== ERRORS ===");
console.log(errors.length ? [...new Set(errors)].join("\n") : "(none)");
fs.writeFileSync(path.join(OUT, "errors.txt"), [...new Set(errors)].join("\n"));
fs.writeFileSync(path.join(OUT, "console.txt"), logs.join("\n"));

await browser.close();
