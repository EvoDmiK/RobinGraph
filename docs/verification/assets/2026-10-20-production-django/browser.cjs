const {chromium}=require('/tmp/robingraph-browser-qa/node_modules/playwright');
const fs=require('node:fs'),assert=require('node:assert/strict');
const base=process.env.QA_BASE_URL||'https://robingraph.dove-nest.com';
(async()=>{const browser=await chromium.launch({headless:true});const rows=[];
try{for(const width of [1280,390,320]){
 const page=await browser.newPage({viewport:{width,height:900},reducedMotion:'reduce'});const errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 const shell=await page.goto(base+'/chat');assert.equal(shell.status(),200);
 await page.locator('#advanced-settings summary').click();
 await page.locator('#chat-intent').selectOption('profile');
 for(const [query,scope,disposition,science] of [['Anas platyrhynchos','korea','answer','Anas platyrhynchos'],['흰뺨검둥오리','all','answer','Anas zonorhyncha']]){
  await page.locator('#species-scope-'+scope).check();
  await page.locator('#profile-name').fill(query);
  await page.locator('#question-input').fill(query);
  const pending=page.waitForResponse(r=>r.url().endsWith('/v1/chat')&&r.request().method()==='POST',{timeout:120000});
  await page.locator('#question-input').press('Enter');
  const response=await pending;assert.equal(response.status(),200);
  const data=await response.json();assert.equal(data.disposition,disposition);assert.ok(JSON.stringify(data).includes(science));
  await page.waitForFunction(()=>!document.querySelector('#question-input').disabled);
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  rows.push({width,query,scope,disposition,passed:true});
 }
 assert.deepEqual(errors,[]);await page.screenshot({path:__dirname+'/django-'+width+'.png',fullPage:true});await page.close();
}
const birds=await browser.newPage();assert.equal((await birds.goto(base+'/birds')).status(),200);await birds.close();
fs.writeFileSync(__dirname+'/browser.json',JSON.stringify({base,response_mocking:false,passed:true,rows,page_errors:0,physical_mobile:false},null,2)+'\n');
console.log(JSON.stringify({passed:true,cases:rows.length,page_errors:0}));
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
