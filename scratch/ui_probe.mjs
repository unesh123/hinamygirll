// Diagnostic probe: load the HINAA web app, capture console/page errors,
// screenshot each view, and exercise the live-voice start path.
import { chromium } from "@playwright/test";
import { mkdirSync } from "node:fs";

const BASE = process.env.HINAA_BASE ?? "http://127.0.0.1:5173";
const OUT = new URL("./probe-out/", import.meta.url).pathname;
mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch({
  args: [
    "--use-fake-device-for-media-stream",
    "--use-fake-ui-for-media-stream",
    "--autoplay-policy=no-user-gesture-required",
  ],
});
const context = await browser.newContext({
  viewport: { width: 1440, height: 900 },
  permissions: ["microphone"],
});
const page = await context.newPage();

const logs = [];
page.on("console", (m) => logs.push(`[${m.type()}] ${m.text()}`));
page.on("pageerror", (e) => logs.push(`[pageerror] ${e.message}`));
page.on("requestfailed", (r) =>
  logs.push(`[requestfailed] ${r.url()} :: ${r.failure()?.errorText}`),
);
page.on("response", (r) => {
  if (r.status() >= 400) logs.push(`[http ${r.status()}] ${r.url()}`);
});

await page.goto(BASE, { waitUntil: "networkidle", timeout: 60000 });
await page.waitForTimeout(3500);
await page.screenshot({ path: `${OUT}01-work.png`, fullPage: false });

// Probe the rendered DOM for basic health
const domInfo = await page.evaluate(() => {
  const root = document.getElementById("root");
  const text = document.body.innerText ?? "";
  return {
    rootChildren: root?.children.length ?? -1,
    textLength: text.length,
    head: text.slice(0, 400),
  };
});

console.log("=== DOM ===");
console.log(JSON.stringify(domInfo, null, 2));

// Navigate to Talk (live voice) view
try {
  const talkBtn = page.getByRole("button", { name: /talk/i }).first();
  if (await talkBtn.count()) {
    await talkBtn.click();
    await page.waitForTimeout(1500);
    await page.screenshot({ path: `${OUT}02-talk.png` });
  } else {
    console.log("!! Talk nav button not found");
  }
} catch (e) {
  console.log("!! talk nav failed:", e.message);
}

console.log("=== CONSOLE (first 120) ===");
console.log(logs.slice(0, 120).join("\n"));

await browser.close();
