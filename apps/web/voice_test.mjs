import { chromium } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const OUT = path.resolve("scratch/voice-test");
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
const wsEvents = [];
const consoleMsgs = [];
page.on("console", (m) => {
  consoleMsgs.push(`[${m.type()}] ${m.text()}`);
});
page.on("pageerror", (e) => errors.push(`pageerror: ${e.message}\n${(e.stack || "").split("\n").slice(0, 6).join("\n")}`));

// Capture WebSocket events by monkey-patching
await page.exposeFunction("_logWsEvent", (e) => wsEvents.push(e));

await page.addInitScript(() => {
  const OriginalWS = window.WebSocket;
  class TrackedWS extends OriginalWS {
    constructor(url, protocols) {
      super(url, protocols);
      window._logWsEvent({ kind: "open", url });
      this.addEventListener("open", () => window._logWsEvent({ kind: "open", url }));
      this.addEventListener("close", (e) => window._logWsEvent({ kind: "close", url, code: e.code, reason: e.reason }));
      this.addEventListener("error", () => window._logWsEvent({ kind: "error", url }));
      const origSend = this.send.bind(this);
      this.send = (data) => {
        const s = typeof data === "string" ? data : `(binary ${data.byteLength ?? "?"}B)`;
        window._logWsEvent({ kind: "send", url, data: s.slice(0, 800) });
        return origSend(data);
      };
      this.addEventListener("message", (e) => window._logWsEvent({ kind: "recv", url, data: String(e.data).slice(0, 1200) }));
    }
  }
  // @ts-ignore
  window.WebSocket = TrackedWS;
});

await page.goto("http://127.0.0.1:5173/", { waitUntil: "domcontentloaded", timeout: 60000 });
await page.waitForTimeout(2500);

// Click the Live Voice / Talk section in the navigation rail
await page.evaluate(() => {
  const navItems = [...document.querySelectorAll('[aria-label]')];
  const talk = navItems.find((n) => /live voice|🎤|talk/i.test(n.getAttribute("aria-label") || ""));
  if (talk) { talk.click(); console.log("Clicked talk nav:", talk.getAttribute("aria-label")); }
  else {
    // Try to find button containing the talk title text
    const all = [...document.querySelectorAll('button, a, [role="button"]')];
    const header = all.find((b) => /live voice|talk to/i.test(b.textContent || ""));
    header?.click();
  }
});
await page.waitForTimeout(2000);

// Find and click Start voice via aria-label
const clicked = await page.evaluate(() => {
  const btns = [...document.querySelectorAll('button')];
  const start = btns.find((b) => /start voice/i.test(b.getAttribute("aria-label") || "") && !/live voice|stop voice/i.test(b.getAttribute("aria-label") || ""));
  if (start) { start.click(); return start.getAttribute("aria-label"); }
  return null;
});
console.log("Start clicked:", clicked);
await page.waitForTimeout(8000);

await page.screenshot({ path: path.join(OUT, "voice-started.png"), fullPage: false });

console.log("\n=== WebSocket events ===");
for (const e of wsEvents) console.log(JSON.stringify(e));

console.log("\n=== Errors ===");
console.log(errors.length ? errors.join("\n---\n") : "(none)");

console.log("\n=== Console (last 40) ===");
console.log(consoleMsgs.slice(-40).join("\n"));

fs.writeFileSync(path.join(OUT, "ws.json"), JSON.stringify(wsEvents, null, 2));
fs.writeFileSync(path.join(OUT, "console.txt"), consoleMsgs.join("\n"));

await browser.close();