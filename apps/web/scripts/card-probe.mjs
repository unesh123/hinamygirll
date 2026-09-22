import { chromium } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";
import { fileURLToPath } from "node:url";

const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..", "..");
const OUT = path.join(REPO_ROOT, ".runtime");
fs.mkdirSync(OUT, { recursive: true });

const WIDTH = Number(process.env.PROBE_W || 1280);
const HEIGHT = Number(process.env.PROBE_H || 900);
const PROMPT =
  process.env.PROBE_PROMPT ||
  "hinaa please search who is mikasa ackerman for me";

const browser = await chromium.launch({
  args: ["--no-sandbox", "--disable-dev-shm-usage"],
});
const page = await browser.newPage({ viewport: { width: WIDTH, height: HEIGHT } });
const errors = [];
page.on("console", (m) => {
  if (m.type() === "error") errors.push(m.text());
});
page.on("pageerror", (e) => errors.push(String(e)));

await page.addInitScript((hideAvatar) => {
  localStorage.setItem(
    "hinaa_settings_v1",
    JSON.stringify({
      _version: 1,
      appearance: {
        theme: "system",
        motion: "system",
        avatarVisible: !hideAvatar,
        avatarStyle: "procedural",
      },
      provider: { preferredMode: "auto", preferredModelByProvider: {} },
    }),
  );
}, !process.env.HINAA_KEEP_AVATAR);

await page.goto("http://127.0.0.1:5173/", { waitUntil: "networkidle", timeout: 60_000 });
await page.waitForTimeout(2_000);

const surface = await page.evaluate(() => {
  const bubble = document.querySelector(".hinaa-work-bubble");
  const chain = [];
  for (let n = bubble; n; n = n.parentElement) {
    const cs = getComputedStyle(n);
    chain.push({
      tag: `${n.tagName.toLowerCase()}.${(n.className || "").toString().split(" ")[0]}`,
      bg: cs.backgroundColor,
    });
  }
  return chain.slice(0, 6);
});
console.log("bubble background chain:", JSON.stringify(surface));

const editor =
  (await page.$("div[contenteditable='true']")) || (await page.$("textarea"));
if (!editor) {
  console.log("NO COMPOSER FOUND");
  await page.screenshot({ path: path.join(OUT, "card-probe-no-composer.png") });
  await browser.close();
  process.exit(2);
}
await editor.click();
await editor.type(PROMPT, { delay: 8 });
await page.keyboard.press("Enter");

const selectors = [
  "section[aria-label='Research sources']",
  "section[aria-label='Public image search results']",
];
let hit = null;
for (let elapsed = 0; elapsed < 150_000 && !hit; elapsed += 2_000) {
  await page.waitForTimeout(2_000);
  for (const sel of selectors) {
    if (await page.$(sel)) {
      hit = sel;
      break;
    }
  }
}

console.log("hit:", hit || "none within 150s");

if (hit) {
  const legibility = await page.evaluate((sel) => {
    const host = document.querySelector(sel);
    const bgOf = (node) => {
      for (let n = node; n; n = n.parentElement) {
        const cs = getComputedStyle(n);
        const m = cs.backgroundColor.match(/rgba?\(([^)]+)\)/);
        if (m) {
          const parts = m[1].split(",").map((x) => parseFloat(x.trim()));
          if (parts.length < 4 || parts[3] > 0.5) {
            return { rgb: parts.slice(0, 3), painted: "color" };
          }
        }
        // A gradient paints the card but is invisible to backgroundColor; the
        // ratio below is then only advisory, so say so instead of assuming white.
        if (cs.backgroundImage && cs.backgroundImage !== "none") {
          return { rgb: [40, 32, 40], painted: "gradient" };
        }
      }
      return { rgb: [255, 255, 255], painted: "none" };
    };
    const lum = (rgb) => {
      const [r, g, b] = rgb.map((v) => {
        const s = v / 255;
        return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
      });
      return 0.2126 * r + 0.7152 * g + 0.0722 * b;
    };
    const ratio = (a, b) => {
      const l1 = Math.max(lum(a), lum(b));
      const l2 = Math.min(lum(a), lum(b));
      return (l1 + 0.05) / (l2 + 0.05);
    };
    const parse = (c) => {
      const m = c.match(/rgba?\(([^)]+)\)/);
      const p = m[1].split(",").map((x) => parseFloat(x.trim()));
      return p.slice(0, 3);
    };
    const rows = [];
    for (const el of host.querySelectorAll("*")) {
      const text = (el.textContent || "").trim();
      if (!text || el.children.length > 0) continue;
      const cs = getComputedStyle(el);
      if (cs.visibility === "hidden" || cs.display === "none") continue;
      const bg = bgOf(el);
      const fg = parse(cs.color);
      rows.push({
        text: text.slice(0, 34),
        color: cs.color,
        bg: `rgb(${bg.rgb.join(",")})`,
        painted: bg.painted,
        contrast: Number(ratio(fg, bg.rgb).toFixed(2)),
        rect: (() => {
          const r = el.getBoundingClientRect();
          return `${Math.round(r.width)}x${Math.round(r.height)} @${Math.round(r.left)},${Math.round(r.top)}`;
        })(),
      });
    }
    return rows;
  }, hit);
  console.log(JSON.stringify(legibility, null, 2));
  const fails = legibility.filter((r) => r.contrast < 3 && r.painted === "color");
  const advisory = legibility.filter((r) => r.contrast < 3 && r.painted !== "color");
  console.log(
    `CONTRAST<3 on a solid backdrop: ${fails.length} of ${legibility.length} (advisory, gradient: ${advisory.length})`,
  );

  const phoneShape = await page.evaluate((sel) => {
    const host = document.querySelector(sel);
    const cards = [...host.querySelectorAll(".source-card")];
    const heights = cards.map((c) => Math.round(c.getBoundingClientRect().height));
    const replyText = document.querySelector(
      ".hinaa-work-bubble p, .hinaa-work-bubble [class*='markdown']",
    );
    const toggle = [...host.querySelectorAll("button")].find((b) =>
      /show (all|fewer) sources/i.test(b.textContent || ""),
    );
    return {
      cardCount: cards.length,
      cardHeights: heights,
      stackHeight: Math.round(host.getBoundingClientRect().height),
      replyTop: replyText ? Math.round(replyText.getBoundingClientRect().top) : null,
      sourcesTop: Math.round(host.getBoundingClientRect().top),
      expanderLabel: toggle ? toggle.textContent.trim() : null,
    };
  }, hit);
  console.log("phoneShape before expand:", JSON.stringify(phoneShape));

  if (phoneShape.expanderLabel) {
    await page.getByRole("button", { name: /show all \d+ sources/i }).click();
    await page.waitForTimeout(700);
    const after = await page.evaluate((sel) => {
      const host = document.querySelector(sel);
      const cards = [...host.querySelectorAll(".source-card")];
      const toggle = [...host.querySelectorAll("button")].find((b) =>
        /show (all|fewer) sources/i.test(b.textContent || ""),
      );
      return {
        cardCount: cards.length,
        stackHeight: Math.round(host.getBoundingClientRect().height),
        expanderLabel: toggle ? toggle.textContent.trim() : null,
      };
    }, hit);
    console.log("phoneShape after expand:", JSON.stringify(after));
  }
}

const hostEl = hit ? await page.$(hit) : null;
if (hostEl) {
  await hostEl.scrollIntoViewIfNeeded().catch(() => {});
  await page.waitForTimeout(600);
  await hostEl.screenshot({ path: path.join(OUT, `card-probe-${WIDTH}.png`) });
}
await page.screenshot({
  path: path.join(OUT, `card-probe-full-${WIDTH}.png`),
  fullPage: false,
});
console.log("consoleErrors:", errors.slice(0, 5));
await browser.close();
