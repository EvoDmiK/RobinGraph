const {chromium}=require('/tmp/robingraph-browser-qa/node_modules/playwright');
const assert=require('node:assert/strict');const fs=require('fs');
const cases=[['Great Spotted Kiwx','Great Spotted Kiwi'],['Okarito Kiwx','Okarito Kiwi'],['North Island Brown Kiwx','North Island Brown Kiwi'],['Keaa','Kea'],['New Zealand Rockwrex','New Zealand Rockwren'],['North Island Kokakx','North Island Kokako']];
(async()=>{const b=await chromium.launch({headless:true});const rows=[];
try{for(const width of [1280,390,320]){
 const p=await b.newPage({viewport:{width,height:1000}});const errors=[];p.on('pageerror',e=>errors.push(String(e)));
 await p.goto('https://robingraph-test.dove-nest.com/chat');await p.locator('#advanced-settings summary').click();
 for(const scope of ['all','outside']){
 await p.locator('#species-scope-'+scope).check();
 for(const [query,english] of cases){
  const expected=scope==='all'&&english==='Kea'?'높은산앵무':english;
  await p.locator('#question-input').fill(query+'에 대해 알려줘');const pending=p.waitForResponse(r=>r.url().endsWith('/v1/chat')&&r.request().method()==='POST',{timeout:180000});
  await p.locator('#question-input').press('Enter');const response=await pending;assert.equal(response.status(),200);const d=await response.json();const resolution=d.entity_resolution||d.resolution;
  assert.equal(d.disposition,'clarify');assert.ok(resolution.candidates.some(c=>c.display_name===expected),query);
  await p.waitForFunction(()=>!document.querySelector('#question-input').disabled);assert.ok((await p.locator('#history').innerText()).includes(expected));
  assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);rows.push({width,scope,query,expected,passed:true});
 }
 }
 assert.deepEqual(errors,[]);await p.screenshot({path:__dirname+`/outside-${width}.png`,fullPage:true});await p.close();
}fs.writeFileSync(__dirname+'/browser.json',JSON.stringify({passed:true,base:'https://robingraph-test.dove-nest.com',rows},null,2)+'\n');}finally{await b.close();}})().catch(e=>{console.error(e);process.exitCode=1});
