/**
 * Mobile layout check — verifies the HINAA stage fits phone-sized viewports.
 *
 * Runs headless Chromium against the dev server, forces the lightweight
 * procedural avatar + mock provider for a deterministic layout, then asserts
 * against the components that actually mount today (topbar-v6, the work
 * surface, composer-v6, the mobile nav).
 *
 * Usage (from apps/web): node scripts/mobile-layout-check.mjs
 *   HINAA_CHROMIUM_PATH=<exe> to use a specific browser; by default Playwright
 *   resolves its own bundled Chromium, which is what works on Windows.
 * Artifacts: screenshots written to <repo root>/.runtime/mobile-<name>.png
 *
 * Note: the check forces the lightweight procedural avatar so layout stays
 * deterministic — the VRM 3D stage uses the same absolute-inset container, so
 * overflow behaviour is equivalent, but the 3D stage itself is not exercised
 * at phone sizes here.
 */

import { chromium } from "@playwright/test";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";

const REPO_ROOT = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
  "..",
  "..",
);
const ARTIFACT_DIR = path.join(REPO_ROOT, ".runtime");
fs.mkdirSync(ARTIFACT_DIR, { recursive: true });

const BASE_URL = process.env.HINAA_WEB_URL || "http://127.0.0.1:5173/";
const VIEWPORTS = [
  { name: "pixel-5-393x851", width: 393, height: 851 },
  { name: "small-android-320x568", width: 320, height: 568 },
];

// Pre-flight: the check needs the Vite dev server running on :5173.
// Fail loudly instead of surfacing cryptic null-layout failures.
try {
  const probe = await fetch(BASE_URL, { method: "HEAD" });
  if (!probe.ok) throw new Error(`HTTP ${probe.status}`);
} catch {
  console.error(
    `Dev server not reachable at ${BASE_URL} — start it with \`pnpm dev\` first.`,
  );
  process.exit(2);
}

const launchOptions = {
  args: [
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--ignore-gpu-blocklist",
    "--enable-webgl",
    "--enable-unsafe-swiftshader",
  ],
};
if (process.env.HINAA_CHROMIUM_PATH) {
  launchOptions.executablePath = process.env.HINAA_CHROMIUM_PATH;
}

const browser = await chromium.launch(launchOptions);
const results = [];

for (const vp of VIEWPORTS) {
  const page = await browser.newPage({
    viewport: { width: vp.width, height: vp.height },
  });
  const consoleErrors = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
  });
  page.on("pageerror", (err) => consoleErrors.push(String(err)));

  // Deterministic layout: procedural avatar + mock provider, avatar on.
  await page.addInitScript(() => {
    try {
      localStorage.setItem(
        "hinaa_settings_v1",
        JSON.stringify({
          _version: 1,
          appearance: {
            theme: "system",
            motion: "system",
            avatarVisible: true,
            avatarStyle: "procedural",
          },
          provider: { preferredMode: "mock", preferredModelByProvider: {} },
        }),
      );
    } catch {
      /* ignore */
    }
  });

  await page.goto(BASE_URL, { waitUntil: "networkidle", timeout: 30_000 }).catch(() => {});
  await page.waitForTimeout(1_500);

  const layout = await page.evaluate(() => {
    const rect = (sel) => {
      const el = document.querySelector(sel);
      if (!el) return null;
      const r = el.getBoundingClientRect();
      return {
        top: Math.round(r.top),
        left: Math.round(r.left),
        right: Math.round(r.right),
        bottom: Math.round(r.bottom),
        width: Math.round(r.width),
        height: Math.round(r.height),
      };
    };
    const doc = document.documentElement;
    const viewport = { w: window.innerWidth, h: window.innerHeight };

    const transcript = document.querySelector(".hinaa-work-transcript");
    const transcriptStyle = transcript ? getComputedStyle(transcript) : null;
    const composer = document.querySelector(".hinaa-work-composer");
    const nav = document.querySelector(".sakura-mobile-nav");

    // A control whose box is taller than one line of its own text is a
    // wrapping pill. getClientRects() cannot tell: a <span> inside a flex
    // button is blockified, so it reports one box no matter how many lines.
    const wrappedControls = [];
    const clippedControls = [];
    const hiddenBehindScroll = [];
    if (composer) {
      for (const control of composer.querySelectorAll("button, [role='button']")) {
        // Controls inside a closed dropdown are not on screen; measuring them
        // reports clips nobody can see.
        const own = control.getBoundingClientRect();
        const visible = typeof control.checkVisibility === "function"
          ? control.checkVisibility()
          : own.width > 1 && own.height > 1;
        if (!visible) continue;
        const label = [...control.childNodes].find(
          (n) => n.nodeType === 3 && n.textContent.trim(),
        ) || control.querySelector("span");
        const text = (label?.textContent || "").trim();
        if (!text) continue;
        const target = label?.nodeType === 3 ? label.parentElement : label;
        const box = target.getBoundingClientRect();
        const lineHeight =
          parseFloat(getComputedStyle(target).lineHeight) ||
          parseFloat(getComputedStyle(target).fontSize) * 1.2;
        if (box.height > lineHeight * 1.5) {
          wrappedControls.push(`${text.slice(0, 24)} (${Math.round(box.height)}px / ${Math.round(lineHeight)}px)`);
        }
        // The usual consequence of stopping a wrap is that an ancestor clips
        // the label instead. The control's own box looks fine — it is the
        // row around it that hides the tail, so compare against every
        // clipping ancestor's client box.
        const box2 = control.getBoundingClientRect();
        for (let node = control.parentElement; node && node !== composer; node = node.parentElement) {
          const overflow = getComputedStyle(node);
          if (!/hidden|auto|scroll|clip/.test(overflow.overflowX)) continue;
          const host = node.getBoundingClientRect();
          if (box2.right <= host.right + 1 && box2.left >= host.left - 1) continue;
          const detail = `${text.slice(0, 24)} (runs to ${Math.round(box2.right)}px, row ends ${Math.round(host.right)}px)`;
          // A row that scrolls still lets him reach the control; a row that
          // clips it leaves the affordance unreachable on a phone.
          if (/auto|scroll/.test(overflow.overflowX)) {
            hiddenBehindScroll.push(detail);
          } else {
            clippedControls.push(detail);
          }
          break;
        }
      }
    }

    return {
      viewport,
      scrollWidth: doc.scrollWidth,
      overflowX: doc.scrollWidth > window.innerWidth + 1,
      topbar: rect(".topbar-v6"),
      workSurface: rect(".hinaa-work-surface"),
      transcript: rect(".hinaa-work-transcript"),
      composer: rect(".hinaa-work-composer"),
      composerCard: rect(".composer-v6"),
      mobileNav: rect(".sakura-mobile-nav"),
      navButtons: [...document.querySelectorAll(".sakura-mobile-nav button")].map((b) => {
        const r = b.getBoundingClientRect();
        return {
          label: (b.getAttribute("aria-label") || b.textContent || "").trim().slice(0, 16),
          inside: r.top >= 0 && r.bottom <= window.innerHeight + 1 && r.left >= -1 && r.right <= window.innerWidth + 1,
        };
      }),
      transcriptScrollable: !!transcriptStyle
        ? /auto|scroll/.test(transcriptStyle.overflowY) &&
          transcript.scrollHeight >= transcript.clientHeight
        : false,
      wrappedControls,
      clippedControls,
      hiddenBehindScroll,
      canvasCount: document.querySelectorAll("canvas").length,
      modelControlRects: [...document.querySelectorAll("[data-testid='composer-model-selector-btn']")].map((el) => {
        const r = el.getBoundingClientRect();
        return {
          w: Math.round(r.width),
          h: Math.round(r.height),
          left: Math.round(r.left),
          right: Math.round(r.right),
          top: Math.round(r.top),
          visible: typeof el.checkVisibility === "function" ? el.checkVisibility() : r.width > 1,
        };
      }),
    };
  });

  const inside = (r) =>
    !!r && r.left >= -1 && r.right <= layout.viewport.w + 1 && r.top >= -1 && r.bottom <= layout.viewport.h + 1;

  // Visible, sized, and actually on screen — a chip pushed past the right edge
  // or scrolled out of view is not a control he can reach.
  const reachableModelControls = layout.modelControlRects.filter(
    (r) => r.visible && r.w > 1 && r.h > 1 && r.top >= 0 && r.top < layout.viewport.h && r.right > 1 && r.left <= layout.viewport.w - 1,
  );

  const checks = {
    noHorizontalOverflow: layout.overflowX === false,
    topbarPresentAndInside: inside(layout.topbar),
    workSurfacePresent: !!layout.workSurface,
    transcriptPresent: !!layout.transcript,
    transcriptScrollsWithoutLibraries: layout.transcriptScrollable,
    composerPresent: !!layout.composer,
    composerInsideViewport: inside(layout.composer),
    // The composer must sit clear of the tab bar, or the last row is untappable.
    composerClearsMobileNav:
      !!layout.composer && !!layout.mobileNav && layout.composer.bottom <= layout.mobileNav.top + 1,
    mobileNavInside: inside(layout.mobileNav),
    allNavButtonsReachable: layout.navButtons.length > 0 && layout.navButtons.every((b) => b.inside),
    noWrappingComposerControls: layout.wrappedControls.length === 0,
    noClippedComposerControls: layout.clippedControls.length === 0,
    // One chip moved to the top bar on a phone; the check fails if that ever
    // leaves him with no way to pick a brain.
    brainControlReachable: reachableModelControls.length >= 1,
    // Chrome above the transcript must not eat the screen: header + any band
    // stay under a quarter of the viewport on a phone.
    chromeWithinBudget:
      !!layout.transcript &&
      layout.transcript.top <= Math.round(layout.viewport.h * 0.25),
    noConsoleErrors: consoleErrors.length === 0,
  };
  const pass = Object.values(checks).every(Boolean);

  await page.screenshot({
    path: path.join(ARTIFACT_DIR, `mobile-${vp.name}.png`),
  });

  results.push({
    viewport: vp.name,
    pass,
    failed: Object.entries(checks).filter(([, ok]) => !ok).map(([k]) => k),
    consoleErrors,
    detail: {
      topbar: layout.topbar,
      transcriptTop: layout.transcript?.top ?? null,
      composer: layout.composer,
      mobileNav: layout.mobileNav,
      wrappedControls: layout.wrappedControls,
      clippedControls: layout.clippedControls,
      hiddenBehindScroll: layout.hiddenBehindScroll,
      canvasCount: layout.canvasCount,
      modelControls: layout.modelControlRects,
      scrollWidth: layout.scrollWidth,
    },
  });
  await page.close();
}

await browser.close();

console.log(JSON.stringify(results, null, 2));
process.exit(results.every((r) => r.pass) ? 0 : 1);
