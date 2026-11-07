import { chromium } from "@playwright/test";
const tag = process.argv[2];
const widths = (process.argv[3]||"1280x800").split(",").map(x=>x.split("x").map(Number));
const sections = (process.argv[4]||"Chat,Dashboard,Models,Reports,Settings").split(",");
const base = "http://127.0.0.1:4192/";
const browser = await chromium.launch({ args: ["--use-gl=angle","--use-angle=swiftshader","--enable-unsafe-swiftshader"] });
for (const [w,h] of widths) {
  const ctx = await browser.newContext({ viewport:{width:w,height:h} });
  const page = await ctx.newPage(); page.setDefaultTimeout(90000);
  const log=[]; page.on("pageerror",e=>log.push("PAGEERR "+e.message.slice(0,200)));
  page.on("console",m=>{ if(m.type()==="error") log.push("CONSOLE "+m.text().slice(0,160)); });
  page.on("response",r=>{ if(r.status()>=400) log.push(`HTTP ${r.status()} ${r.url()}`); });
  await page.goto(base,{waitUntil:"domcontentloaded"});
  await page.waitForTimeout(3000);
  const shot = async n => { await page.screenshot({path:`/tmp/verify/ui2/${tag}-${w}-${n}.png`,timeout:90000,animations:"disabled"}); };
  if (process.env.WITH_COMPANION) await shot("home-with-companion");
  await page.evaluate(()=>document.querySelector('[aria-label="Hide Companion"]')?.click());
  await page.waitForTimeout(800);
  for (const s of sections) {
    const t0=Date.now();
    try {
      await page.evaluate((s)=>{ const el=[...document.querySelectorAll('nav button, aside button, nav a')].find(b=>b.textContent.trim().startsWith(s)); if(!el) throw new Error("nav item not found "+s); el.click(); }, s);
      await page.waitForTimeout(1500);
      await shot(s.replace(/\W/g,""));
      log.push(`ok ${s} ${Date.now()-t0}ms`);
    } catch(e){ log.push(`FAIL ${s}: ${e.message.slice(0,100)}`); }
  }
  console.log("==",w,h); console.log([...new Set(log)].join("\n"));
  await ctx.close();
}
await browser.close();
