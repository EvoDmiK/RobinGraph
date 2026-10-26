const {chromium}=require('/tmp/robingraph-browser-qa/node_modules/playwright');
const fs=require('node:fs'),assert=require('node:assert/strict');
const base='https://robingraph-test.dove-nest.com';
(async()=>{const browser=await chromium.launch({headless:true});const rows=[];
try{for(const width of [1280,390]){
 const page=await browser.newPage({viewport:{width,height:900},reducedMotion:'reduce'}),errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 assert.equal((await page.goto(base+'/chat')).status(),200);
 const checks=[
 ['청둥오리와 흰뺨검둥오리는 어떤 관계야?','answer','Anas'],
 ['참새목 중 열매를 먹고 사는 새는?','answer','열매'],
 ['숲에 사는 새중에 직박구리랑 같은 열매를 먹는 새는?','abstain','특정 식물'],
 ['한국에 기록된 오리 중 청둥오리와 같은 속인 종은?','answer','국내 기록'],
 ];
 for(let i=0;i<checks.length;i++){
  const [question,disposition,needle]=checks[i];
  if(i===3){await page.locator('#advanced-settings summary').click();await page.locator('#chat-intent').selectOption('profile');}
  await page.locator('#question-input').fill(question);
  const next=page.waitForResponse(r=>r.url().endsWith('/v1/chat')&&r.request().method()==='POST',{timeout:180000});
  await page.locator('#question-input').press('Enter');const response=await next;assert.equal(response.status(),200);
  const data=await response.json();assert.equal(data.disposition,disposition);assert.equal(data.result.kind,'graph_query');
  await page.waitForFunction(()=>!document.querySelector('#question-input').disabled);
  const panel=page.locator('.graph-query-answer').last();await panel.waitFor({state:'visible'});
  assert.ok((await panel.textContent()).includes(needle));
  const folds=panel.locator('details');
  for (const fold of await folds.all()) { assert.equal(await fold.evaluate(e=>e.open),false); }
  if(disposition==='abstain'){assert.ok((await panel.innerText()).includes(needle));}
  if(i===1){
    const firstEvidence=panel.locator('.graph-query-species-row details').first();
    const toggle=firstEvidence.locator('summary');await toggle.focus();await toggle.press('Enter');assert.equal(await firstEvidence.evaluate(e=>e.open),true);
    assert.ok(await firstEvidence.locator('a').first().isVisible());await toggle.press('Enter');
    const notes=panel.locator('.graph-query-notes');await notes.locator('summary').click();assert.equal(await notes.evaluate(e=>e.open),true);await notes.locator('summary').click();
  }
  if(disposition==='answer'){assert.ok(await panel.locator('a[href^="https://"]').count());assert.ok(await panel.locator('button').count());}
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  if(i===1){await panel.evaluate(e=>e.scrollIntoView({block:'start'}));await page.screenshot({path:__dirname+'/graph-query-'+width+'.png'});}
  rows.push({width,question,disposition,rendered:true,source_links:await panel.locator('a').count(),passed:true});
 }
 const panel=page.locator('.graph-query-answer').last();const button=panel.locator('button').first();
 const next=page.waitForResponse(r=>r.url().endsWith('/v1/chat')&&r.request().method()==='POST',{timeout:180000});
 await button.click();const response=await next;assert.equal(response.status(),200);const body=await response.json();
 assert.equal(body.disposition,'answer');assert.equal(body.result.kind,'profile');
 await page.waitForFunction(()=>!document.querySelector('#question-input').disabled);
 assert.deepEqual(errors,[]);rows.push({width,graph_species_button_opens_profile:true,page_errors:0,passed:true});
 await page.close();
}
fs.writeFileSync(__dirname+'/browser.json',JSON.stringify({base,response_mocking:false,passed:true,rows,physical_mobile:false},null,2)+'\n');
console.log('Actual TEST browser checks passed:',rows.length);
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
