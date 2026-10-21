const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
(async()=>{
 const browser=await chromium.launch({headless:true});const rows=[];
 try {
  for(const width of [1280,390,320]) {
   const page=await browser.newPage({viewport:{width,height:1000}});const errors=[];const posts=[];
   page.on('pageerror',e=>errors.push(String(e)));
   await page.route('**/*',route=>route.request().method()==='POST'?(posts.push(new URL(route.request().url()).pathname),route.abort()):route.continue());
   await page.goto('https://robingraph.dove-nest.com/chat');
   await page.locator('#advanced-settings summary').click();
   await page.locator('#question-input').fill('작성 중 질문');
   await page.locator('#species-scope-outside').check();
   assert.equal(await page.locator('#question-input').inputValue(),'작성 중 질문');
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
   assert.deepEqual(errors,[]);assert.equal(posts.filter(p=>p==='/v1/chat').length,0);
   await page.screenshot({path:__dirname+`/production-${width}.png`,fullPage:true});
   rows.push({width,passed:true,blockedPostPaths:posts,pageErrors:errors});await page.close();
  }
  fs.writeFileSync(__dirname+'/browser-readonly.json',JSON.stringify({passed:true,base:'https://robingraph.dove-nest.com',scope:'Live Production GET/static UI; POST blocked; Chromium viewport emulation, no API response mocks',rows},null,2)+'\n');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
