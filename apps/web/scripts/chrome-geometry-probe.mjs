/**
 * Geometry probe for the phone chrome: what actually sits in each band at
 * 320px and 393px, and which control falls outside its row.
 *
 * HINAA_WEB_URL=<url> node scripts/chrome-geometry-probe.mjs
 */
import { chromium } from "@playwright/test";

const BASE_URL = process.env.HINAA_WEB_URL || "http://127.0.0.1:5173/";
const VIEWPORTS = [
  { name: "393x851", width: 393, height: 851 },
  { name: "320x568", width: 320, height: 568 },
];

const browser = await chromium.launch({
  args: ["--no-sandbox", "--disable-dev-shm-usage"],
});

for (const vp of VIEWPORTS) {
  const page = await browser.newPage({ viewport: { width: vp.width, height: vp.height } });
  await page.addInitScript(() => {
    try {
      localStorage.setItem(
        "hinaa_settings_v1",
        JSON.stringify({
          _version: 1,
          appearance: { theme: "system", motion: "system", avatarVisible: true, avatarStyle: "procedural" },
          provider: { preferredMode: "mock", preferredModelByProvider: {} },
        }),
      );
    } catch {
      /* ignore */
    }
  });
  await page.goto(BASE_URL, { waitUntil: "networkidle", timeout: 30_000 }).catch(() => {});
  await page.waitForTimeout(1_200);

  const out = await page.evaluate(() => {
    const describe = (el) => {
      const r = el.getBoundingClientRect();
      const cs = getComputedStyle(el);
      return {
        cls: (el.className || "").toString().slice(0, 40),
        tag: el.tagName.toLowerCase(),
        text: (el.textContent || "").trim().slice(0, 22),
        x: Math.round(r.left),
        right: Math.round(r.right),
        y: Math.round(r.top),
        w: Math.round(r.width),
        h: Math.round(r.height),
        overflowX: cs.overflowX,
      };
    };
    const bands = [];
    for (const sel of [".topbar-v6", ".hinaa-work-surface > header", ".sakura-mobile-nav", ".hinaa-work-composer"]) {
      for (const el of document.querySelectorAll(sel)) bands.push(describe(el));
    }
    // Every leaf control in the composer, with the first clipping ancestor.
    const composer = document.querySelector(".hinaa-work-composer");
    const controls = [];
    if (composer) {
      for (const el of composer.querySelectorAll("button, [role='button'], input, textarea")) {
        const r = el.getBoundingClientRect();
        if (r.width < 1 || r.height < 1) continue;
        if (!el.checkVisibility?.()) continue;
        let clip = null;
        for (let n = el.parentElement; n && n !== composer.parentElement; n = n.parentElement) {
          const ov = getComputedStyle(n).overflowX;
          if (!/hidden|auto|scroll|clip/.test(ov)) continue;
          const host = n.getBoundingClientRect();
          if (r.right > host.right + 1 || r.left < host.left - 1) {
            clip = { host: (n.className || "").toString().slice(0, 40), hostRight: Math.round(host.right), ovf: ov };
            break;
          }
        }
        controls.push({ ...describe(el), clip, scrollW: el.parentElement?.scrollWidth ?? null });
      }
    }
    const rows = [];
    for (const el of composer ? composer.querySelectorAll("*") : []) {
      const cs = getComputedStyle(el);
      if (!/flex|grid/.test(cs.display)) continue;
      if (el.children.length < 2) continue;
      const r = el.getBoundingClientRect();
      if (r.width < 40 || r.height < 12) continue;
      rows.push({ cls: (el.className || "").toString().slice(0, 40), w: Math.round(r.width), h: Math.round(r.height), y: Math.round(r.top), overflowX: cs.overflowX, scrollW: el.scrollWidth, kids: el.children.length });
    }
    return { bands, controls, rows: rows.filter((x) => x.scrollW > x.w + 1 || x.overflowX !== "visible") };
  });

  console.log(`\n===== ${vp.name} (innerWidth ${vp.width}) =====`);
  console.log("BANDS");
  for (const b of out.bands) console.log(`  ${b.tag}.${b.cls} y=${b.y} h=${b.h} w=${b.w} ovf=${b.overflowX}`);
  console.log("COMPOSER CONTROLS");
  for (const c of out.controls)
    console.log(`  "${c.text}" x=${c.x}..${c.right} y=${c.y} w=${c.w} h=${c.h}${c.clip ? `  CLIPPED-BY .${c.clip.host} (ends ${c.clip.hostRight}, ${c.clip.ovf})` : ""}`);
  console.log("ROWS THAT SCROLL OR CLIP");
  for (const r of out.rows) console.log(`  .${r.cls} w=${r.w} scrollW=${r.scrollW} h=${r.h} y=${r.y} ovf=${r.overflowX} kids=${r.kids}`);
  await page.close();
}

await browser.close();
