import { chromium } from "/tmp/hoplite/workspace/node_modules/.pnpm/playwright@1.62.0/node_modules/playwright/index.mjs";
const tag = process.argv[2], port = process.argv[3];
const b = await chromium.launch({ args: ["--use-gl=angle","--use-angle=swiftshader","--enable-unsafe-swiftshader"] });
const p = await b.newPage({ viewport: { width: 1280, height: 800 } });
p.on("pageerror", e => console.log("pageerror", e.message));
await p.goto(`http://127.0.0.1:${port}/`, { waitUntil: "domcontentloaded" });
await p.waitForTimeout(12000);
const panel = p.locator('[data-testid="work-companion-panel"]').first();
const bb = await panel.boundingBox({timeout:60000});
const shot = n => p.screenshot({ path:`/tmp/verify/avatar/${tag}-${n}.png`, clip:{x:bb.x,y:bb.y,width:bb.width,height:bb.height}, timeout:90000, animations:"disabled" });
await shot("idle");
console.log("hooked", await p.evaluate(() => {
  const c = document.querySelector("canvas"); const k = Object.keys(c).find(k=>k.startsWith("__reactFiber")); let f = c[k];
  while (f) { const pr = f.memoizedProps; if (pr && pr.speechBridge) {
    const t0 = performance.now(); const keys=["aa","ih","ou","ee","oh"]; const events=[];
    for (let i=0;i<800;i++) events.push({ timeMs: i*150, durationMs: 150, mouth: keys[i%5], weight: 0.85 });
    pr.speechBridge.current = { utteranceId: 99, state: "playing", source: "browser", timingSource: "text", events, calibrationMs: 0, elapsedMs: () => performance.now()-t0, timing: null };
    pr.speakingRef.current = true; return "ok"; } f = f.return; }
  return "notfound"; }));
await p.waitForTimeout(25000);
for (let i=0;i<4;i++){ await shot("speak-"+i); await p.waitForTimeout(6000); }
console.log("done");
await b.close();
