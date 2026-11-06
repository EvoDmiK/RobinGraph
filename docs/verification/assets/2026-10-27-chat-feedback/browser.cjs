const {chromium}=require('/tmp/rg212-browser-qa/node_modules/playwright');
const fs=require('fs'),assert=require('node:assert/strict');
const out=__dirname;
(async()=>{const browser=await chromium.launch();const rows=[],errors=[];try{
 const p=await browser.newPage({viewport:{width:1280,height:960},reducedMotion:'reduce'});
 p.on('pageerror',e=>errors.push(e.message));
 await p.goto('https://robingraph-test.dove-nest.com/chat',{waitUntil:'networkidle'});
 const cases=[{rating:'helpful',label:'도움됐어요',question:'청둥오리에 대해 알려줘'},
 {rating:'misunderstood',label:'질문을 잘못 이해했어요',question:'청둥오리와 서식지가 겹치면서 먹이가 다른 새는?'},
 {rating:'incorrect',label:'답변이 틀렸어요',question:'청둥오리랑 비슷한 식생을 가진 새는?'}];
 for(const c of cases){
  const before=p.waitForResponse(r=>r.url().endsWith('/v1/chat')&&r.request().method()==='POST',{timeout:120000});
  await p.locator('#question-input').fill(c.question);await p.locator('#question-input').press('Enter');
  const response=await before;assert.equal(response.status(),200);const body=await response.json();
  const headers=response.headers(),token=headers['x-robingraph-feedback-token'],traceId=headers['x-robingraph-trace-id'];
  assert.ok(token&&traceId);fs.writeFileSync(out+'/browser-pending-'+c.rating+'.json',JSON.stringify({...c,trace_id:traceId,response:body},null,2));const answer=p.locator('.message-answer').last();
  const button=answer.getByRole('button',{name:c.label,exact:true});await button.waitFor();
  let attempts=[],saved=false;
  for(let attempt=0;attempt<4;attempt++){
   const vote=p.waitForResponse(r=>r.url().endsWith('/v1/chat/feedback')&&r.request().method()==='POST');
   await button.click();const r=await vote;const payload=await r.json();attempts.push({status:r.status(),body:payload});
   if(r.status()===200){saved=true;break;}
   assert.equal(r.status(),503);await p.waitForTimeout(2000);
  }
  assert.ok(saved,'Feedback did not become available');
  await p.waitForFunction(()=>[...document.querySelectorAll('.answer-feedback-status')].at(-1).textContent.includes('감사'));
  assert.equal(await button.getAttribute('aria-pressed'),'true');
  assert.equal(await answer.locator('.answer-feedback-button:disabled').count(),3);
  const retry=await p.evaluate(async({token,rating})=>{const rows=[];for(const value of [rating,rating==='incorrect'?'helpful':'incorrect']){const r=await fetch('/v1/chat/feedback',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token,rating:value})});rows.push({status:r.status,body:await r.json()});}return rows;},{token,rating:c.rating});
  assert.deepEqual(retry.map(r=>r.status),[200,409]);
  const invalid=await p.evaluate(async()=>{const r=await fetch('/v1/chat/feedback',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token:'tampered',rating:'helpful'})});return {status:r.status,body:await r.json()};});assert.equal(invalid.status,400);
  await answer.locator('.answer-feedback').scrollIntoViewIfNeeded();
  assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  await p.screenshot({path:out+'/desktop-'+c.rating+'.png'});
  rows.push({...c,trace_id:traceId,chat_status:response.status(),response:body,feedback_attempts:attempts,retries:retry,tampered:invalid});
  fs.writeFileSync(out+'/browser-results.json',JSON.stringify({rows,page_errors:errors,response_mocking:false,automated_test_feedback:true},null,2));
 }
 await p.setViewportSize({width:390,height:844});const last=p.locator('.answer-feedback').last();await last.scrollIntoViewIfNeeded();
 assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
 await p.screenshot({path:out+'/mobile-feedback.png'});assert.deepEqual(errors,[]);
 const api=await p.evaluate(async()=>{const rows=[];for(const path of ['/health','/openapi.json']){const r=await fetch(path);const body=await r.json();rows.push({path,status:r.status,body:path==='/openapi.json'?{feedback_route:!!body.paths['/v1/chat/feedback']}:body});}return rows;});
 assert.ok(api.every(x=>x.status===200));assert.equal(api[0].body.deployment_target,'test');
 fs.writeFileSync(out+'/browser-results.json',JSON.stringify({rows,api,page_errors:errors,response_mocking:false,automated_test_feedback:true,viewports:[1280,390],physical_mobile:false},null,2));
 console.log(JSON.stringify({chat_cases:rows.length,feedback_saved:rows.length,identical_retry_status:200,changed_vote_status:409,invalid_token_status:400,page_errors:errors,viewports:[1280,390]}));
}finally{await browser.close();}})().catch(e=>{console.error(e.message);process.exitCode=1});
