import { chromium } from "/tmp/hoplite/workspace/node_modules/.pnpm/playwright@1.62.0/node_modules/playwright/index.mjs";
const tag = process.argv[2], m = process.argv[3], speak = process.argv[4] === "speak", n = +(process.argv[5]||4), gap=+(process.argv[6]||1500);
const b = await chromium.launch({ args: ["--use-gl=angle","--use-angle=swiftshader","--enable-unsafe-swiftshader"] });
const p = await b.newPage({ viewport: { width: 1280, height: 800 } });
p.on("pageerror", e => console.log("pageerror", e.message));
await p.goto("http://127.0.0.1:4181/", { waitUntil: "domcontentloaded" });
await p.waitForTimeout(9000);
const panel = p.locator('[data-testid="work-companion-panel"]').first();
const bb = await panel.boundingBox({timeout:60000});
for (let i=0;i<8;i++){
  const btn = p.locator('[aria-label^="Change avatar camera from"]').first();
  const label = await btn.getAttribute("aria-label");
  if (label.includes("from "+m)) break;
  await btn.evaluate(el=>el.click()); await p.waitForTimeout(400);
}
if (speak) console.log("hooked", await p.evaluate(() => {
  const c = document.querySelector("canvas"); if(!c) return "nocanvas";
  const k = Object.keys(c).find(k=>k.startsWith("__reactFiber")); let f = c[k];
  while (f) { const pr = f.memoizedProps; if (pr && pr.speakingRef && pr.jawEnergy !== undefined || (pr && pr.speakingRef)) { window.__spk = pr.speakingRef; pr.speakingRef.current = true; return "ok"; } f = f.return; }
  return "notfound";
}));
await p.waitForTimeout(9000);
for (let f=0;f<n;f++){
  await p.screenshot({ path:`/tmp/verify/avatar/${tag}-${m}-${speak?"speak":"idle"}-${f}.png`, clip:{x:bb.x,y:bb.y,width:bb.width,height:bb.height}, timeout:90000, animations:"disabled" });
  await p.waitForTimeout(gap);
}
console.log("done");
await b.close();
