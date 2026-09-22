import { chromium } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..", "..");
const WIDTH = Number(process.env.PROBE_W || 393);
const HEIGHT = Number(process.env.PROBE_H || 851);

const browser = await chromium.launch({ args: ["--no-sandbox", "--disable-dev-shm-usage"] });
const page = await browser.newPage({ viewport: { width: WIDTH, height: HEIGHT } });

await page.addInitScript((hideAvatar) => {
  localStorage.setItem(
    "hinaa_settings_v1",
    JSON.stringify({
      _version: 1,
      appearance: { theme: "system", motion: "system", avatarVisible: !hideAvatar, avatarStyle: "procedural" },
      provider: { preferredMode: "auto", preferredModelByProvider: {} },
    }),
  );
}, !process.env.HINAA_KEEP_AVATAR);

await page.goto("http://127.0.0.1:5173/", { waitUntil: "networkidle", timeout: 60_000 });
await page.waitForTimeout(3_000);

const report = await page.evaluate(() => {
  const rect = (sel) => {
    const el = document.querySelector(sel);
    if (!el) return null;
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    return {
      top: Math.round(r.top),
      bottom: Math.round(r.bottom),
      h: Math.round(r.height),
      w: Math.round(r.width),
      position: cs.position,
      overflowY: cs.overflowY,
      scrollTop: Math.round(el.scrollTop),
      scrollHeight: Math.round(el.scrollHeight),
      clientHeight: Math.round(el.clientHeight),
    };
  };
  const cards = [...document.querySelectorAll(".source-card")].map((el) => {
    const r = el.getBoundingClientRect();
    return { h: Math.round(r.height), w: Math.round(r.width), top: Math.round(r.top) };
  });
  const section = document.querySelector("section[aria-label='Research sources']");
  const BRAIN_TEXT = /^(auto\s*\(router\)|auto|hina\s*brain|claude|gpt|gemini|deepseek|qwen|llama|agnes|omni|groq)/i;
  const bandOf = (el) => {
    for (const band of ["topbar-v6", "hinaa-work-composer", "sakura-mobile-nav", "hinaa-stage"]) {
      if (el.closest(`.${band}`)) return band;
    }
    return "other";
  };
  const modelControls = [];
  for (const el of document.querySelectorAll("button, [role='button'], select, [aria-haspopup]")) {
    const text = (el.textContent || "").replace(/\s+/g, " ").trim();
    const aria = (el.getAttribute("aria-label") || "").trim();
    if (!BRAIN_TEXT.test(text) && !BRAIN_TEXT.test(aria)) continue;
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) continue;
    modelControls.push({
      text: text.slice(0, 42) || aria.slice(0, 42),
      band: bandOf(el),
      top: Math.round(r.top),
      h: Math.round(r.height),
      w: Math.round(r.width),
    });
  }
  return {
    windowScrollY: Math.round(window.scrollY),
    docScrollTop: Math.round(document.documentElement.scrollTop),
    bodyScrollTop: Math.round(document.body.scrollTop),
    topbar: rect(".topbar-v6"),
    shell: rect(".hinaa-shell"),
    appShell: rect(".sakura-app-shell"),
    stage: rect(".hinaa-stage"),
    transcript: rect(".hinaa-work-transcript"),
    composer: rect(".hinaa-work-composer"),
    mobileNav: rect(".sakura-mobile-nav"),
    modelControls,
    researchSection: section ? { h: Math.round(section.getBoundingClientRect().height) } : null,
    cardCount: cards.length,
    cards: cards.slice(0, 4),
    totalCardsHeight: cards.reduce((a, c) => a + c.h, 0),
  };
});

console.log(JSON.stringify(report, null, 2));
await page.screenshot({ path: path.join(REPO_ROOT, ".runtime", `chrome-${WIDTH}.png`) });
await browser.close();
