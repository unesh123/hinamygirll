// Where does the PDF card get lost in the browser?
// The backend renders the file (a sidecar appears on disk), but the thread can
// show prose instead of a download card. This records every link in the chain:
// stream tool/plan events, the /tools/execute round trip, the approval UI, and
// the DOM the user is left looking at.
//
//   node scripts/pdf-chain-probe.mjs [prompt]
import { chromium } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";
import { fileURLToPath } from "node:url";

const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..", "..");
const OUT = path.join(REPO_ROOT, ".runtime");
fs.mkdirSync(OUT, { recursive: true });
const PROMPT = process.argv[2] || "make me a pdf about quantum computing";
const BASE_URL = process.env.PROBE_URL || "https://hinaa-workspace.vercel.app/";
const WIDTH = Number(process.env.PROBE_W || 1280);
const HEIGHT = Number(process.env.PROBE_H || 900);

const browser = await chromium.launch({ args: ["--no-sandbox", "--disable-dev-shm-usage"] });
const page = await browser.newPage({ viewport: { width: WIDTH, height: HEIGHT } });
const consoleErrors = [];
const streamEvents = [];
const executions = [];

page.on("console", (m) => {
  if (m.type() === "error") consoleErrors.push(m.text());
});
page.on("pageerror", (e) => consoleErrors.push(String(e)));

page.on("response", async (res) => {
  const url = res.url();
  if (url.includes("/conversations/turns:stream")) {
    try {
      const body = await res.text();
      for (const line of body.split("\n")) {
        if (!line.trim()) continue;
        let obj;
        try {
          obj = JSON.parse(line);
        } catch {
          continue;
        }
        const type = obj.type || "";
        if (type.startsWith("tool.") || type === "plan" || type.includes("error")) {
          streamEvents.push({ type, payload: JSON.stringify(obj).slice(0, 900) });
        }
      }
    } catch {
      /* the stream body can already be consumed by the app */
    }
  }
  if (url.includes("/tools/execute") || url.includes("/tools/poll")) {
    let snippet = null;
    try {
      snippet = (await res.text()).slice(0, 700);
    } catch {
      /* body unavailable */
    }
    executions.push({ url: url.replace(/^https?:\/\/[^/]+/, ""), status: res.status(), snippet });
  }
});

await page.addInitScript(() => {
  localStorage.setItem(
    "hinaa_settings_v1",
    JSON.stringify({
      _version: 1,
      appearance: { theme: "system", motion: "system", avatarVisible: false, avatarStyle: "procedural" },
      provider: { preferredMode: "auto", preferredModelByProvider: {} },
    }),
  );
});

await page.goto(BASE_URL, { waitUntil: "domcontentloaded", timeout: 60_000 });
await page.waitForTimeout(3_000);

const editor = (await page.$("div[contenteditable='true']")) || (await page.$("textarea"));
if (!editor) {
  console.log("NO COMPOSER");
  await page.screenshot({ path: path.join(OUT, "pdf-chain-no-composer.png") });
  await browser.close();
  process.exit(2);
}
await editor.click();
await editor.type(PROMPT, { delay: 8 });
await page.keyboard.press("Enter");

const snapshot = () =>
  page.evaluate(() => {
    const buttons = [...document.querySelectorAll("button")]
      .map((b) => (b.textContent || "").trim())
      .filter((t) => /pdf|confirm|approve|allow|run|download/i.test(t));
    const bubbles = [...document.querySelectorAll(".hinaa-work-bubble")];
    const last = bubbles[bubbles.length - 1];
    return {
      downloadAnchors: document.querySelectorAll("a[download]").length,
      approvalButtons: buttons.slice(0, 8),
      activityRows: [...document.querySelectorAll("[class*='toolActivity'], [data-tool-activity]")]
        .map((n) => (n.textContent || "").trim().slice(0, 90))
        .slice(0, 6),
      bubbleTail: last ? (last.innerText || "").replace(/\s+/g, " ").slice(-700) : null,
      bubbleHasRawHash: last ? /(^|\s)#{1,3}\s/.test(last.innerText || "") : null,
      cardText: (() => {
        const link = document.querySelector("a[download]");
        if (!link) return null;
        const host = link.closest("div[style*='margin-top']") || link.parentElement;
        return (host.innerText || "").replace(/\s+/g, " ").slice(0, 400);
      })(),
    };
  });

let seen = null;
for (let elapsed = 0; elapsed < 240_000; elapsed += 4_000) {
  await page.waitForTimeout(4_000);
  seen = await snapshot();
  if (seen.downloadAnchors > 0) {
    console.log(`card appeared after ~${elapsed + 4}s`);
    break;
  }
  if (seen.approvalButtons.length) {
    console.log(`approval affordance at ~${elapsed + 4}s: ${JSON.stringify(seen.approvalButtons)}`);
    break;
  }
}

console.log(JSON.stringify({ prompt: PROMPT, finalDom: seen }, null, 2));
console.log("--- stream tool/plan events ---");
for (const e of streamEvents) console.log(`${e.type}: ${e.payload}`);
console.log("--- execute/poll round trips ---");
for (const e of executions) console.log(`${e.url} -> ${e.status} ${e.snippet}`);
console.log("consoleErrors:", JSON.stringify(consoleErrors.slice(0, 6)));

await page.screenshot({ path: path.join(OUT, "pdf-chain-final.png"), fullPage: false });
fs.writeFileSync(path.join(OUT, "pdf-chain-events.json"), JSON.stringify({ streamEvents, executions, consoleErrors }, null, 2));
await browser.close();
