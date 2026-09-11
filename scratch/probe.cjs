const { chromium } = require("playwright");

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  const msgs = [];
  const errors = [];
  page.on("console", (m) => {
    msgs.push(`[${m.type()}] ${m.text()}`);
  });
  page.on("pageerror", (e) => {
    errors.push(`PAGEERROR: ${e.message}`);
  });
  page.on("requestfailed", (r) => {
    errors.push(`REQFAIL: ${r.url()} ${r.failure()?.errorText}`);
  });
  const url = process.argv[2] || "http://127.0.0.1:5174/";
  try {
    await page.goto(url, { waitUntil: "networkidle", timeout: 30000 });
  } catch (e) {
    errors.push("GOTO: " + e.message.split("\n")[0]);
  }
  await page.waitForTimeout(3500);
  const rootHtml = await page.evaluate(() => {
    const r = document.getElementById("root");
    return r ? { childCount: r.childElementCount, htmlLen: r.innerHTML.length, snippet: r.innerHTML.slice(0, 400) } : null;
  });
  await page.screenshot({ path: "C:/Users/unesh/OneDrive/all my cloud stroge/Desktop/APPS/HINAMYGIRL/scratch/probe.png", fullPage: false });
  console.log("=== ROOT ===");
  console.log(JSON.stringify(rootHtml, null, 2));
  console.log("=== PAGE ERRORS (" + errors.length + ") ===");
  console.log(errors.slice(0, 40).join("\n"));
  console.log("=== CONSOLE (" + msgs.length + ") ===");
  console.log(msgs.slice(0, 80).join("\n"));
  await browser.close();
})();
