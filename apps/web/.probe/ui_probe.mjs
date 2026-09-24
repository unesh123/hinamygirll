// Diagnostic probe: load the HINAA web app, capture console/page errors,
// screenshot each view, and exercise the live-voice start path.
import { chromium } from "@playwright/test";
import { mkdirSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const BASE = process.env.HINAA_BASE ?? "http://127.0.0.1:5173";
const OUT = path.join(path.dirname(fileURLToPath(import.meta.url)), "probe-out");
mkdirSync(OUT, { recursive: true });
const shot = (n) => path.join(OUT, n);

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
const push = (s) => {
  logs.push(s);
  console.log(s);
};
page.on("console", (m) => {
  const t = m.text();
  if (m.type() === "warning" && /THREE|WebGL|VRMUtils|GPU stall/.test(t)) return;
  push(`[${m.type()}] ${t}`);
});
page.on("pageerror", (e) => push(`[pageerror] ${e.message}`));
page.on("requestfailed", (r) =>
  push(`[requestfailed] ${r.url()} :: ${r.failure()?.errorText}`),
);
page.on("response", (r) => {
  if (r.status() >= 400) push(`[http ${r.status()}] ${r.url()}`);
});
page.on("websocket", (ws) => {
  push(`[ws open] ${ws.url()}`);
  ws.on("socketerror", (e) => push(`[ws error] ${ws.url()} :: ${e}`));
  ws.on("close", () => push(`[ws close] ${ws.url()}`));
});

await page.goto(BASE, { waitUntil: "domcontentloaded", timeout: 60000 });
await page.waitForTimeout(6000);
await page.screenshot({ path: shot("01-work.png") });

const domInfo = await page.evaluate(() => {
  const text = document.body.innerText ?? "";
  return { textLength: text.length, head: text.slice(0, 600) };
});
console.log("=== DOM ===", JSON.stringify(domInfo, null, 2));

// ── Talk view ───────────────────────────────────────────────
try {
  const talkBtn = page.getByRole("button", { name: /talk/i }).first();
  if (await talkBtn.count()) {
    await talkBtn.click();
    await page.waitForTimeout(4000);
    await page.screenshot({ path: shot("02-talk.png") });
  } else {
    console.log("!! Talk nav button not found");
  }
} catch (e) {
  console.log("!! talk nav failed:", e.message);
}

// ── Start live voice ────────────────────────────────────────
try {
  const startBtn = page
    .getByRole("button", { name: /start live|start voice|start/i })
    .first();
  if (await startBtn.count()) {
    await startBtn.click();
  } else {
    console.log("!! start button not found; body text:");
    console.log(await page.evaluate(() => document.body.innerText.slice(0, 800)));
  }
} catch (e) {
  console.log("!! start click failed:", e.message);
}
await page.waitForTimeout(12000);
await page.screenshot({ path: shot("03-voice.png") });
console.log(
  "=== TALK TEXT ===\n",
  await page.evaluate(() => document.body.innerText.slice(0, 1500)),
);

console.log("=== SUMMARY: errors ===");
console.log(logs.filter((l) => /pageerror|\[error\]|\[http |requestfailed/.test(l)).join("\n"));

await browser.close();
