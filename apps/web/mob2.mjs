import { chromium } from "@playwright/test";
const tag=process.argv[2];
const browser = await chromium.launch({ args: ["--use-gl=angle","--use-angle=swiftshader","--enable-unsafe-swiftshader"] });
const ctx = await browser.newContext({ viewport:{width:390,height:844}, hasTouch:true, isMobile:true });
const page = await ctx.newPage(); page.setDefaultTimeout(90000);
const log=[]; page.on("pageerror",e=>log.push("PAGEERR "+e.message.slice(0,200)));
page.on("console",m=>{ if(m.type()==="error") log.push("CONSOLE "+m.text().slice(0,160)); });
page.on("response",r=>{ if(r.status()>=400) log.push(`HTTP ${r.status()} ${r.url()}`); });
await page.goto("http://127.0.0.1:4182/",{waitUntil:"domcontentloaded"});
await page.waitForTimeout(3000);
const click=async t=>page.evaluate(t=>{const el=[...document.querySelectorAll('button')].find(b=>b.textContent.trim()===t||b.getAttribute('aria-label')===t); if(!el) throw new Error("no "+t); el.click();},t);
for (const t of ["Dashboard","Models","Reports","Settings"]) {
  try { await click("More options"); await page.waitForTimeout(900); if(t==="Dashboard") await page.screenshot({path:`/tmp/verify/ui2/${tag}-mob-More.png`,timeout:90000,animations:"disabled"});
    await click(t); await page.waitForTimeout(2000);
    await page.screenshot({path:`/tmp/verify/ui2/${tag}-mob-${t}.png`,timeout:90000,animations:"disabled"}); log.push("ok "+t); } catch(e){ log.push("FAIL "+t+" "+e.message.slice(0,80)); }
  if (t==="Settings") await page.evaluate(()=>document.querySelector('[aria-label*="lose"]')?.click());
}
log.push("scrollW "+await page.evaluate(()=>document.documentElement.scrollWidth));
console.log([...new Set(log)].join("\n"));
await browser.close();
