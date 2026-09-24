const { chromium } = require("playwright");

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  const all = [];
  page.on("console", (m) => all.push(`[${m.type()}] ${m.text()}`));
  page.on("pageerror", (e) => all.push(`PAGEERROR: ${e.message}`));
  page.on("requestfailed", (r) => all.push(`REQFAIL: ${r.url().split("/").slice(-2).join("/")} ${r.failure()?.errorText}`));
  await page.goto("http://127.0.0.1:5173/", { waitUntil: "domcontentloaded", timeout: 30000 });
  await page.waitForTimeout(2500);

  // Capture the visible text on the page
  const visibleText = await page.evaluate(() => document.body.innerText.slice(0, 800));
  console.log("=== INITIAL VISIBLE TEXT ===\n" + visibleText);

  // Locate the "Start voice" button by its aria-label and title
  const startBtn = page.locator('button[aria-label="Start voice"], button[title="Start voice"]').first();
  const count = await page.locator('button[aria-label="Start voice"], button[title="Start voice"]').count();
  console.log(`\n=== Start voice buttons found: ${count} ===`);

  if (count > 0) {
    await startBtn.click();
    await page.waitForTimeout(2500);
    const afterText = await page.evaluate(() => document.body.innerText.slice(0, 800));
    console.log("=== AFTER CLICK VISIBLE TEXT ===\n" + afterText);
  }

  await page.screenshot({ path: "C:/Users/unesh/OneDrive/all my cloud stroge/Desktop/APPS/HINAMYGIRL/scratch/probe-voice.png", fullPage: false });

  console.log("\n=== CONSOLE/PAGE LOG (last 60) ===");
  console.log(all.slice(-60).join("\n"));
  await browser.close();
})();