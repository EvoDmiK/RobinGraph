const { chromium } = require('/tmp/robingraph-browser-qa/node_modules/playwright');
const fs = require('node:fs'), assert = require('node:assert/strict');
(async () => {
 const browser = await chromium.launch({headless:true}); const rows=[];
 try {
  for (const width of [390,1280]) {
   const page=await browser.newPage({viewport:{width,height:900},reducedMotion:'reduce'});const errors=[];page.on('pageerror',e=>errors.push(e.message));
   assert.equal((await page.goto('https://robingraph-test.dove-nest.com/chat')).status(),200);
   for (const food of ['곤충','고기']) {
    const question=`까마귀과 중에서 ${food}${food==='곤충'?'을':'를'} 먹는 새는?`;
    await page.locator('#question-input').fill(question);
    const pending=page.waitForResponse(r=>r.url().endsWith('/v1/chat')&&r.request().method()==='POST');await page.locator('#question-input').press('Enter');
    const data=await(await pending).json();assert.equal(data.disposition,'answer');assert.equal(data.result.payload.status,'answer');assert.ok(data.result.payload.items.length);
    await page.waitForFunction(()=>!document.querySelector('#question-input').disabled);
    const panel=page.locator('.graph-query-answer').last();await panel.waitFor({state:'visible'});await panel.locator('.graph-query-notes summary').click();const text=await panel.innerText();assert.ok(text.includes(food));
    assert.ok(!text.includes('질문의 조건을 모두 확인하지 못했습니다'));
    await panel.evaluate(e=>e.scrollIntoView({block:'start'}));assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
    await page.screenshot({path:__dirname+`/query-${food}-${width}.png`});
    rows.push({width,question,status:data.disposition,item_count:data.result.payload.items.length,page_errors:[...errors],overflow:false,response_mocking:false});
   }
   await page.locator('#question-input').fill('왜가리에 대해 알고 싶어');const pending=page.waitForResponse(r=>r.url().endsWith('/v1/chat')&&r.request().method()==='POST');await page.locator('#question-input').press('Enter');
   const data=await(await pending).json();assert.equal(data.result.kind,'profile');await page.waitForFunction(()=>!document.querySelector('#question-input').disabled);
   await page.locator('.species-diet-icons:visible').first().waitFor({state:'visible'});
   const text=await page.locator('.species-diet-icons').allTextContents();assert.ok(text.some(t=>t.includes('곤충')&&t.includes('고기')&&t.includes('물고기')));
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);assert.deepEqual(errors,[]);
   await page.screenshot({path:__dirname+`/profile-${width}.png`});rows.push({width,question:'왜가리에 대해 알고 싶어',diet_labels:text,page_errors:errors,overflow:false,response_mocking:false});
   await page.close();
  }
  fs.writeFileSync(__dirname+'/browser.json',JSON.stringify({browser:'Chromium',physical_mobile:false,rows},null,2)+'\n');console.log('6 actual public browser cases passed');
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
