const {chromium}=require('/tmp/robingraph-browser-qa/node_modules/playwright');
const fs=require('node:fs'),assert=require('node:assert/strict');
const phase=process.argv[2]||'candidate';const receipt=JSON.parse(fs.readFileSync(__dirname+'/candidate-release.json'));const base=phase==='public'?'https://robingraph-test.dove-nest.com':receipt.base;
(async()=>{const browser=await chromium.launch({headless:true});const rows=[];try{
for(const width of [1280,390]){const page=await browser.newPage({viewport:{width,height:900},reducedMotion:'reduce'});const errors=[];page.on('pageerror',e=>errors.push(e.message));assert.equal((await page.goto(base+'/chat')).status(),200);
for(const [key,question,expected] of [
['original','까마귀과면서 열매를 먹는 새는 어떤 종이 있어?','answer'],
['composite','까마귀과 중 숲에 살고 열매를 먹는 새는?','answer'],
['measure','까마귀과 중 부리 길이 콧구멍 기준이 5mm 이상인 새는?','answer'],
['subspecies','Corvus corone corone 중 숲에 사는 새는?','abstain'],
['negation','까마귀과 중 숲에 살지 않는 새는?','clarify'],
['label-conflict','물까마귀과 중 숲에 사는 새는?','abstain']]){
await page.locator('#question-input').fill(question);const next=page.waitForResponse(r=>r.url().endsWith('/v1/chat')&&r.request().method()==='POST');await page.locator('#question-input').press('Enter');const response=await next;assert.equal(response.status(),200);const d=await response.json();assert.equal(d.disposition,expected,question);await page.waitForFunction(()=>!document.querySelector('#question-input').disabled);
if(expected==='answer'){const panel=page.locator('.graph-query-answer').last();assert.ok(await panel.locator('.graph-query-species-row').count());await panel.evaluate(e=>e.scrollIntoView({block:'start'}));}
assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);assert.deepEqual(errors,[]);await page.screenshot({path:__dirname+'/'+phase+'-'+key+'-'+width+'.png'});rows.push({width,key,question,status:d.disposition,item_count:d.result.payload?.items?.length||0,page_errors:0,passed:true});}
await page.close();}
fs.writeFileSync(__dirname+'/browser-'+phase+'.json',JSON.stringify({phase,base,response_mocking:false,physical_mobile:false,browser:'Chromium',rows},null,2)+'\n');console.log('Actual '+phase+' browser:',rows.length,'passed');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
