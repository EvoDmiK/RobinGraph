const {chromium}=require('/tmp/robingraph-browser-qa/node_modules/playwright');
const fs=require('node:fs'),assert=require('node:assert/strict');
(async()=>{const browser=await chromium.launch({headless:true});const rows=[];try{
for(const width of [1280,390]){const page=await browser.newPage({viewport:{width,height:900},reducedMotion:'reduce'});const errors=[];page.on('pageerror',e=>errors.push(e.message));
assert.equal((await page.goto('https://robingraph-test.dove-nest.com/chat')).status(),200);
for(const [key,question,expected] of [
['natural','열매 먹는 참새목 새를 찾아 줘','answer'],
['shared','숲에서 살면서 직박구리와 식성이 같은 새가 궁금해','answer'],
['negation','참새목 중 열매를 안 먹는 새는?','clarify'],
['plant','참새목 중 감나무 열매를 먹는 새는?','abstain']]){
await page.locator('#question-input').fill(question);const next=page.waitForResponse(r=>r.url().endsWith('/v1/chat')&&r.request().method()==='POST');await page.locator('#question-input').press('Enter');const response=await next;assert.equal(response.status(),200);const d=await response.json();assert.equal(d.disposition,expected);
await page.waitForFunction(()=>!document.querySelector('#question-input').disabled);if(expected==='answer'){const panel=page.locator('.graph-query-answer').last();assert.ok(await panel.locator('.graph-query-species-row').count());await panel.evaluate(e=>e.scrollIntoView({block:'start'}));}
assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);assert.deepEqual(errors,[]);await page.screenshot({path:__dirname+'/'+key+'-'+width+'.png'});rows.push({width,key,question,status:d.disposition,item_count:d.result.payload?.items?.length||0,page_errors:0,passed:true});}
await page.close();}
fs.writeFileSync(__dirname+'/browser.json',JSON.stringify({response_mocking:false,physical_mobile:false,browser:'Chromium',rows},null,2)+'\n');console.log('Actual public TEST browser:',rows.length,'passed');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
