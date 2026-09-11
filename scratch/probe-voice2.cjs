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

  // Click "Talk to HINAA" tile
  const talkTile = page.getByText("Talk to HINAA").first();
  await talkTile.click();
  await page.waitForTimeout(2000);

  const afterSwitch = await page.evaluate(() => document.body.innerText.slice(0, 1200));
  console.log("=== AFTER SWITCH VISIBLE TEXT ===\n" + afterSwitch);

  // Locate and click Start voice
  const count = await page.locator('button[aria-label="Start voice"], button[title="Start voice"]').count();
  console.log(`\n=== Start voice buttons: ${count} ===`);
  if (count > 0) {
    await page.locator('button[aria-label="Start voice"], button[title="Start voice"]').first().click();
    await page.waitForTimeout(3500);
    const afterVoice = await page.evaluate(() => document.body.innerText.slice(0, 1200));
    console.log("=== AFTER START VOICE ===\n" + afterVoice);
    await page.screenshot({ path: "C:/Users/unesh/OneDrive/all my cloud stroge/Desktop/APPS/HINAMYGIRL/scratch/probe-voice.png", fullPage: false });
  } else {
    await page.screenshot({ path: "C:/Users/unesh/OneDrive/all my cloud stroge/Desktop/APPS/HINAMYGIRL/scratch/probe-talk.png", fullPage: false });
  }

  console.log("\n=== CONSOLE/PAGE LOG (last 50) ===");
  console.log(all.slice(-50).join("\n"));
  await browser.close();
})();