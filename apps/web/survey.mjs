import { chromium } from "playwright";
const tag = process.argv[2] || "before";
const base = "http://127.0.0.1:4182/";
const sections = ["Chat","Runway 3D","Dashboard","Models","Reports","VIP Deep Vault","Settings"];
const browser = await chromium.launch({ args: ["--use-gl=angle","--use-angle=swiftshader","--enable-unsafe-swiftshader"] });
const sizes = [["desk",1440,900],["w1280",1280,800],["mob",390,844]];
for (const [name,w,h] of sizes) {
  const ctx = await browser.newContext({ viewport:{width:w,height:h} });
  const page = await ctx.newPage();
  const errs=[]; page.on("pageerror",e=>errs.push("PAGEERR "+e.message.slice(0,200)));
  page.on("console",m=>{ if(m.type()==="error") errs.push("CONSOLE "+m.text().slice(0,200)); });
  page.on("response",r=>{ if(r.status()>=400) errs.push(`HTTP ${r.status()} ${r.url()}`); });
  await page.goto(base,{waitUntil:"domcontentloaded",timeout:60000});
  await page.waitForTimeout(4000);
  const hide = page.getByRole("button",{name:"Hide Companion"});
  if (await hide.count()) await hide.first().click({timeout:20000}).catch(e=>errs.push("hide fail "+e.message.slice(0,80)));
  await page.waitForTimeout(500);
  await page.screenshot({path:`/tmp/verify/ui2/${tag}-${name}-home.png`,timeout:60000,animations:"disabled"}).catch(e=>errs.push("shot fail home"));
  if (name!=="mob") for (const s of sections) {
    const t0=Date.now();
    try {
      await page.locator("nav, aside").getByText(s,{exact:true}).first().click({timeout:20000});
      await page.waitForTimeout(1200);
      await page.screenshot({path:`/tmp/verify/ui2/${tag}-${name}-${s.replace(/\W/g,"")}.png`,timeout:60000,animations:"disabled"});
      errs.push(`ok ${s} ${Date.now()-t0}ms`);
    } catch(e){ errs.push(`FAIL ${s}: ${e.message.slice(0,100)}`); }
  }
  console.log("==",name); console.log([...new Set(errs)].join("\n"));
  await ctx.close();
}
await browser.close();
