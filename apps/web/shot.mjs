import { chromium } from "/tmp/hoplite/workspace/node_modules/.pnpm/playwright@1.62.0/node_modules/playwright/index.mjs";
const tag = process.argv[2] || "before";
const modes = (process.argv[3] || "portrait").split(",");
const b = await chromium.launch({ args: ["--use-gl=angle","--use-angle=swiftshader","--enable-unsafe-swiftshader"] });
const p = await b.newPage({ viewport: { width: 1280, height: 800 } });
p.on("pageerror", e => console.log("pageerror", e.message));
await p.goto("http://127.0.0.1:4181/", { waitUntil: "domcontentloaded" });
await p.waitForTimeout(9000);
const panel = p.locator('[data-testid="work-companion-panel"]').first();
console.log("panel", await panel.count(), JSON.stringify(await panel.boundingBox()));
for (const m of modes) {
  for (let i=0;i<8;i++){
    const btn = p.locator('[aria-label^="Change avatar camera from"]').first();
    const label = await btn.getAttribute("aria-label");
    if (label.toLowerCase().includes("from "+m) ) break;
    await btn.click(); await p.waitForTimeout(600);
  }
  await p.waitForTimeout(2500);
  for (let f=0;f<3;f++){
    const bb=await panel.boundingBox(); await p.screenshot({ path:`/tmp/verify/avatar/${tag}-${m}-${f}.png`, clip:{x:bb.x,y:bb.y,width:bb.width,height:bb.height}, timeout:90000, animations:"disabled" });
    await p.waitForTimeout(500);
  }
  console.log("shot", m);
}
await b.close();
