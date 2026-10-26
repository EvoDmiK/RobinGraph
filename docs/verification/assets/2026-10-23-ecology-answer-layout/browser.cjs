const {chromium}=require('/tmp/robingraph-browser-qa/node_modules/playwright');
const fs=require('node:fs'),assert=require('node:assert/strict');
(async()=>{const browser=await chromium.launch({headless:true}),rows=[];try{
 for(const width of [390,1280])for(const name of ['청둥오리','천둥오리'])for(const [label,relation] of [['식성·먹이 생태 범주','trophic_niche'],['서식 환경','habitat']]){
  const page=await browser.newPage({viewport:{width,height:1000},reducedMotion:'reduce'}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('https://robingraph-test.dove-nest.com/chat');const steps=[];
  async function step(action){const pending=page.waitForResponse(r=>r.url().endsWith('/v1/chat')&&r.request().method()==='POST',{timeout:90000});await action();const response=await pending,data=await response.json();steps.push({request:response.request().postDataJSON(),response:data});await page.waitForFunction(()=>!document.querySelector('#question-input').disabled,null,{timeout:90000});return data;}
  await page.locator('#question-input').fill(`${name}랑 비슷한 식생을 가진 새들을 알려줘`);
  let data=await step(()=>page.locator('#question-input').press('Enter'));
  assert.equal(data.disposition,'clarify');assert.equal(data.result.choices.length,2);
  data=await step(()=>page.getByRole('group',{name:'질문 의미 선택',exact:true}).last().getByRole('button',{name:label,exact:true}).click());
  if(name==='천둥오리'){
   assert.equal(data.disposition,'clarify');assert.equal(data.entity_resolution.status,'candidates');
   assert.ok(data.entity_resolution.candidates.some(c=>c.scientific_name==='Anas platyrhynchos'));
   data=await step(()=>page.getByRole('group',{name:'추천 새 이름 후보',exact:true}).last().getByRole('button',{name:'청둥오리 (Anas platyrhynchos) 선택하여 질문하기',exact:true}).click());
  }
  assert.equal(data.disposition,'answer');assert.equal(data.result.question_answer.topic,'ecological_related');
  assert.deepEqual(data.result.question_answer.relations.groups.map(g=>g.relation),[relation]);
  assert.ok(data.result.question_answer.items.length>0);assert.deepEqual(errors,[]);
  const result=page.locator('.species-question-answer[data-ecological="true"]').last();
  await result.locator('.ecological-peer').first().waitFor();
  assert.equal(await result.locator('.question-answer-facts').count(),0);
  assert.equal(await result.locator('.ecological-peer').count(),3);
  assert.equal(await result.getByRole('button',{name:'같은 서식 환경·먹이 생태의 새 살펴보기',exact:true}).count(),0);
  const source=result.locator('.ecological-group > details').first();
  assert.equal(await source.evaluate(el=>el.open),false);
  await source.locator(':scope > summary').focus();await page.keyboard.press('Enter');
  assert.equal(await source.evaluate(el=>el.open),true);
  assert.ok(await source.locator('a[href]').count()>0);
  await page.keyboard.press('Enter');assert.equal(await source.evaluate(el=>el.open),false);
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);assert.equal(overflow,false);
  await page.locator('.message-answer').last().evaluate(el=>el.scrollIntoView({block:'start'}));
  await page.screenshot({path:__dirname+`/${name}-${relation}-${width}.png`,fullPage:true});
  let comparisonVerified=false,popupVerified=false;
  if(width===1280 && name==='청둥오리' && relation==='trophic_niche') {
    await page.locator('[data-ecological-reference="true"] > button').last().click();
    assert.ok(await page.locator('dialog[open]').count());
    await page.keyboard.press('Escape');assert.equal(await page.locator('dialog[open]').count(),0);popupVerified=true;
    await result.locator('.comparison-peer-choose').first().focus();await page.keyboard.press('Enter');
    await page.locator('.species-comparison').last().waitFor({timeout:90000});comparisonVerified=true;
  }
  rows.push({width,name,label,relation,steps,page_errors:errors,overflow,source_keyboard_toggle:true,comparisonVerified,popupVerified,response_mocking:false});await page.close();
 }
 fs.writeFileSync(__dirname+'/browser.json',JSON.stringify({browser:'Chromium',physical_mobile:false,rows},null,2)+'\n');console.log(JSON.stringify({passed:rows.length,viewports:[390,1280],response_mocking:false}));
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
