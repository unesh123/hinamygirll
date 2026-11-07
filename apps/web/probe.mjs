import { chromium } from "/tmp/hoplite/workspace/node_modules/.pnpm/playwright@1.62.0/node_modules/playwright/index.mjs";
const b = await chromium.launch({ args: ["--use-gl=angle","--use-angle=swiftshader","--enable-unsafe-swiftshader"] });
const p = await b.newPage({ viewport: { width: 1280, height: 800 } });
await p.goto(`http://127.0.0.1:4182/`, { waitUntil: "domcontentloaded" });
await p.waitForTimeout(12000);
console.log(JSON.stringify(await p.evaluate(() => {
  const c = document.querySelector("canvas"); const k = Object.keys(c).find(k=>k.startsWith("__reactFiber")); let f = c[k];
  const out = {canvas:[c.width,c.height,c.clientWidth,c.clientHeight]};
  while (f) { let h = f.memoizedState; let n=0; while (h && n<80) { const v=h.memoizedState; if (v && typeof v==="object" && "hipsY" in v) out.anatomy=v; h=h.next; n++; } f=f.return; }
  return out;
})));
await b.close();
