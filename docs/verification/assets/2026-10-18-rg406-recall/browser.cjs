const {chromium}=require('/tmp/robingraph-browser-qa/node_modules/playwright');
const assert=require('assert/strict');const fs=require('fs');
(async()=>{const b=await chromium.launch({headless:true});const rows=[];
try{for(const width of [1280,390,320]){
 const p=await b.newPage({viewport:{width,height:1000}});const errors=[];p.on('pageerror',e=>errors.push(String(e)));
 await p.goto('https://robingraph-test.dove-nest.com/chat');await p.locator('#advanced-settings summary').click();
 for(const [scope,query,expected] of [['outside','높은산앵무아','Kea'],['korea','천둥오리','청둥오리'],['unknown','타조아','타조']]){
  await p.locator('#species-scope-'+scope).check();await p.locator('#question-input').fill(query+'에 대해 알려줘');
  const reply=p.waitForResponse(r=>r.url().endsWith('/v1/chat')&&r.request().method()==='POST',{timeout:180000});
  await p.locator('#question-input').press('Enter');const response=await reply;assert.equal(response.status(),200);
  const data=await response.json();const resolution=data.entity_resolution||data.resolution;
  assert.equal(data.disposition,'clarify');assert.equal(resolution.candidates[0].display_name,expected);
  await p.waitForFunction(()=>!document.querySelector('#question-input').disabled);
  assert.ok((await p.locator('#history').innerText()).includes(expected));
  assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  if(scope==='outside')await p.screenshot({path:__dirname+`/outside-${width}.png`,fullPage:true});
  rows.push({width,scope,query,expected,passed:true});
 }
 assert.deepEqual(errors,[]);await p.close();
}fs.writeFileSync(__dirname+'/browser.json',JSON.stringify({passed:true,base:'https://robingraph-test.dove-nest.com',rows},null,2)+'\n');}finally{await b.close();}})().catch(e=>{console.error(e);process.exitCode=1});
