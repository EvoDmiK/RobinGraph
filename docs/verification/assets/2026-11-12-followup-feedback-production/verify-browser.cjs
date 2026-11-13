'use strict';
const fs=require('fs'),cp=require('child_process'),os=require('os'),path=require('path'),assert=require('assert').strict;
const out='/tmp/robingraph-followup-feedback-prod-20261112',origin=process.argv[2]||'https://robingraph.dove-nest.com';
assert.ok(['https://robingraph.dove-nest.com','http://192.168.219.97:8000'].includes(origin));
const profile=fs.mkdtempSync(path.join(os.tmpdir(),'rg-review-actual-'));let browser,socket,diagnose;
const delay=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{
 browser=cp.spawn('/Users/kimdove/Library/Caches/ms-playwright/chromium_headless_shell-1248/chrome-headless-shell-mac-arm64/chrome-headless-shell',['--headless','--mute-audio','--disable-background-networking','--no-first-run','--remote-debugging-port=0','--user-data-dir='+profile],{stdio:['ignore','ignore','pipe']});
 let startup='';const debuggerUrl=await new Promise((resolve,reject)=>{browser.stderr.on('data',d=>{startup+=d;const m=startup.match(/DevTools listening on (ws:\/\/\S+)/);if(m)resolve(m[1]);});setTimeout(()=>reject(Error('Chromium startup timeout')),15000).unref();});
 const port=new URL(debuggerUrl).port,targets=await(await fetch('http://127.0.0.1:'+port+'/json/list')).json();
 const target=targets[0]||await(await fetch('http://127.0.0.1:'+port+'/json/new?about:blank',{method:'PUT'})).json();
 socket=new WebSocket(target.webSocketDebuggerUrl);await new Promise(r=>socket.addEventListener('open',r));
 let seq=0;const pending=new Map(),requests=[],exceptions=[];
 socket.addEventListener('message',e=>{const d=JSON.parse(e.data);if(d.id){const p=pending.get(d.id);pending.delete(d.id);d.error?p.reject(Error('CDP command failed')):p.resolve(d.result);}else if(d.method==='Network.requestWillBeSent'){requests.push({url:d.params.request.url,method:d.params.request.method});}else if(d.method==='Runtime.exceptionThrown'){exceptions.push('Page JavaScript exception');}});
 const send=(method,params={})=>new Promise((resolve,reject)=>{const id=++seq;pending.set(id,{resolve,reject});socket.send(JSON.stringify({id,method,params}));});
 const evaluate=async expression=>{const r=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true,userGesture:true});if(r.exceptionDetails)throw Error('Browser evaluation failed');return r.result.value;};
 diagnose=()=>evaluate(`({url:location.href,title:document.title,status:document.querySelector('#status-message')?.textContent,answers:document.querySelectorAll('.message-answer').length,questions:window.__verify?.chats.map(x=>x.request.question),feedback_statuses:window.__verify?.votes.map(x=>x.status)})`);
 const wait=async expression=>{for(let i=0;i<700;i++){if(await evaluate(expression))return;await delay(100);}throw Error('Browser condition timeout');};
 await send('Page.enable');await send('Runtime.enable');await send('Network.enable');
 await send('Emulation.setDeviceMetricsOverride',{width:1280,height:1000,deviceScaleFactor:1,mobile:false});



 const runId='rg213-rg603-prod-20261112-'+Date.now();
 const records=[],guards=[],votes=[];
 function save(){fs.writeFileSync(out+'/browser-results.json',JSON.stringify({run_id:runId,origin,rows:records,guards,votes,automated_verification:true,not_human_gold:true,response_mocking:false},null,2));}
 await send('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-motion',value:'reduce'}]});
 await send('Page.navigate',{url:origin+'/chat'});await wait(`document.readyState==='complete' && !!document.querySelector('#question-input')`);
 const health=await evaluate(`fetch('/health').then(r=>r.json())`);assert.equal(health.deployment_target,'prod');assert.equal(health.status,'ok');
 await evaluate(`(()=>{window.__verify={chats:[],votes:[]};const native=window.fetch.bind(window);window.fetch=async function(input,init){const r=await native(input,init);const u=typeof input==='string'?input:input.url;if(u==='/v1/chat'||u==='/v1/chat/feedback'){const body=await r.clone().json();const request=JSON.parse(init.body);const row={request,status:r.status,body,headers:{trace_id:r.headers.get('X-RobinGraph-Trace-Id'),feedback_token:r.headers.get('X-RobinGraph-Feedback-Token'),cache_control:r.headers.get('Cache-Control')}};(u==='/v1/chat'?window.__verify.chats:window.__verify.votes).push(row);}return r;};})()`);
 const safe=`function clean(v){if(Array.isArray(v))return v.map(clean);if(v&&typeof v==='object')return Object.fromEntries(Object.entries(v).map(([k,x])=>[k,/token|followup_context/i.test(k)?'[redacted]':clean(x)]));return v;}`;
 const capture=async(label,index)=>{
  const row=await evaluate(`(()=>{${safe};const r=window.__verify.chats[${index}];return {label:${JSON.stringify(label)},request:clean(r.request),status:r.status,response:clean(r.body),trace_id:r.headers.trace_id,feedback_token_present:!!r.headers.feedback_token,followup_token_present:!!r.body.followup_context,cache_control:r.headers.cache_control};})()`);
  assert.equal(row.status,200);assert.ok(row.trace_id);assert.ok(row.feedback_token_present);assert.equal(row.cache_control,'no-store');records.push(row);save();return row;
 };
 const chat=async(label,question)=>{
  const n=await evaluate(`window.__verify.chats.length`);
  await evaluate(`(()=>{const e=document.querySelector('#question-input');e.value=${JSON.stringify(question)};e.dispatchEvent(new Event('input',{bubbles:true}));document.querySelector('#chat-form').requestSubmit();})()`);
  await wait(`window.__verify.chats.length>${n} && !document.querySelector('#question-input').disabled && document.querySelectorAll('.message-answer').length>${n}`);
  return capture(label,n);
 };
 async function vote(rating,keyboard){
  const chatIndex=records.length-1,n=await evaluate(`window.__verify.votes.length`);
  const label={helpful:'도움됐어요',misunderstood:'질문을 잘못 이해했어요',incorrect:'답변이 틀렸어요'}[rating];
  await wait(`(()=>{const a=[...document.querySelectorAll('.message-answer')].at(-1);return !![...a.querySelectorAll('.answer-feedback-button')].find(b=>b.textContent===${JSON.stringify(label)});})()`);
  await evaluate(`(()=>{const a=[...document.querySelectorAll('.message-answer')].at(-1);const b=[...a.querySelectorAll('.answer-feedback-button')].find(b=>b.textContent===${JSON.stringify(label)});b.scrollIntoView({block:'center'});${keyboard?'b.focus()':'b.click()'};})()`);
  if(keyboard){await send('Input.dispatchKeyEvent',{type:'keyDown',key:'Enter',code:'Enter',text:String.fromCharCode(13),windowsVirtualKeyCode:13});await send('Input.dispatchKeyEvent',{type:'keyUp',key:'Enter',code:'Enter',windowsVirtualKeyCode:13});}
  await wait(`window.__verify.votes.length>${n}`);
  const first=await evaluate(`window.__verify.votes[${n}].status`);votes.push({label:records[chatIndex].label,trace_id:records[chatIndex].trace_id,rating,keyboard,first_status:first});save();assert.equal(first,200,'First feedback submission must succeed');
  await wait(`(()=>{const a=[...document.querySelectorAll('.message-answer')].at(-1);return a.querySelectorAll('.answer-feedback-button:disabled').length===3;})()`);
  const retry=await evaluate(`(async()=>{const c=window.__verify.chats[${chatIndex}],rows=[];for(const rating of [${JSON.stringify(rating)},${JSON.stringify(rating==='incorrect'?'helpful':'incorrect')}]){const r=await fetch('/v1/chat/feedback',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token:c.headers.feedback_token,rating})});rows.push(r.status);}return rows;})()`);
  assert.deepEqual(retry,[200,409]);votes.at(-1).retry_statuses=retry;save();console.log('Feedback verified: '+rating);
 }
 const base=await chat('chain.base','숲에 사는 열매 먹는 새');assert.equal(base.response.result.payload.status,'answer');assert.equal(base.followup_token_present,true);
 const baseConditions=base.response.result.payload.conditions.map(c=>c.label);assert.equal(baseConditions.length,2);
 await vote('helpful',true);
 const korea=await chat('chain.korea','그중 한국에서 볼 수 있는 새는?');assert.equal(korea.response.followup.status,'applied');assert.equal(korea.response.followup.plan.scope,'korea');assert.deepEqual(korea.response.followup.plan.conditions,baseConditions);
 await vote('misunderstood',false);
 const empty=await chat('chain.empty','그중 체중 5000g 이상인 새는?');assert.equal(empty.response.disposition,'abstain');assert.equal(empty.response.result.payload.status,'empty');assert.ok(empty.response.followup.plan.conditions.some(x=>x.includes('5000')));assert.deepEqual(empty.response.followup.retained,korea.response.followup.retained);
 const emptyText=await evaluate(`document.querySelectorAll('.message-answer')[2].innerText`);assert.ok(emptyText.includes('이번 조회 조건'));assert.ok(emptyText.includes('다음 질문 유지 조건'));
 await vote('incorrect',false);
 const number=await chat('chain.number','그 새들 중 체중 100g 이상인 새는?');assert.equal(number.response.result.payload.status,'answer');assert.equal(number.response.followup.plan.scope,'korea');assert.ok(number.response.followup.plan.conditions.some(x=>x.includes('100g')));assert.ok(!number.response.followup.plan.conditions.some(x=>x.includes('5000')));
 assert.ok(baseConditions.every(c=>number.response.followup.plan.conditions.includes(c)));
 console.log('Condition retention and empty-result recovery verified');
 // Guard requests use an actual signed base response; opaque values never leave browser memory.
 const cases=[
  ['guard.missing','그중 열매 먹는 새','context_missing','missing'],
  ['guard.forged','그중 열매 먹는 새','context_invalid','forged'],
  ['guard.scope','그중 한국에서 볼 수 있는 새는?','context_scope_mismatch','scope'],
  ['guard.negation','그중 열매 안 먹는 새','unsupported_addition','normal'],
  ['guard.multiple','그중 한국에서 볼 수 있는 습지에 사는 새','multiple_additions','normal'],
  ['guard.conflict','그중 습지에 사는 새','conflicting_condition','normal'],
  ['guard.duplicate','그중 열매 먹는 새','duplicate_condition','normal'],
  ['guard.route','그중 한국에서 볼 수 있는 새는?','route_conflict','route']
 ];
 for(const [label,question,reason,mode] of cases){
  const index=await evaluate(`window.__verify.chats.length`);
  await evaluate(`(async()=>{const p={question:${JSON.stringify(question)},intent:'auto',species_scope:'all',defer_enrichment:true,defer_discovery:true};const mode=${JSON.stringify(mode)};if(mode!=='missing')p.followup_context=mode==='forged'?'invalid':window.__verify.chats[0].body.followup_context;if(mode==='scope')p.species_scope='outside';if(mode==='route')p.intent='taxonomy';await fetch('/v1/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(p)});})()`);
  const row=await capture(label,index);assert.equal(row.response.disposition,'clarify');assert.equal(row.response.followup.status,'rejected');assert.equal(row.response.followup.reason,reason);guards.push({label,reason,passed:true});save();
 }
 const invalid=await evaluate(`(async()=>{const r=await fetch('/v1/chat/feedback',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token:'tampered',rating:'helpful'})});return r.status;})()`);assert.equal(invalid,400);
 for(const width of [1280,390]){
  await send('Emulation.setDeviceMetricsOverride',{width,height:960,deviceScaleFactor:1,mobile:width<600});
  const layout=await evaluate(`({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,scheme:getComputedStyle(document.documentElement).colorScheme})`);assert.equal(layout.width,layout.scrollWidth);assert.ok(layout.scheme.includes('light'));
  const shot=await send('Page.captureScreenshot',{format:'png'});fs.writeFileSync(out+'/production-'+width+'.png',Buffer.from(shot.data,'base64'));
 }
 // Only four messages above were sent through the UI; guard requests did not alter its state.
 await evaluate(`document.querySelector('#species-scope-outside').click()`);
 assert.equal(await evaluate(`document.querySelector('#followup-context-bar').hidden`),true);
 await evaluate(`document.querySelector('#clear-button').click()`);
 assert.equal(await evaluate(`document.querySelector('#followup-context-bar').hidden`),true);
 assert.equal(exceptions.length,0);
 const report={run_id:runId,origin,rows:records,guards,votes,tampered_feedback_status:invalid,health:{target:health.deployment_target,status:health.status},page_errors:exceptions,scope_change_clears_context:true,clear_clears_context:true,response_mocking:false,automated_verification:true,not_human_gold:true,viewports:[1280,390],physical_mobile_tested:false,app_changed:false};
 fs.writeFileSync(out+'/browser-results.json',JSON.stringify(report,null,2));console.log(JSON.stringify({run_id:runId,chats:records.length,guard_cases:guards.length,feedback_saved:votes.length,page_errors:exceptions.length}));await send('Browser.close');
})().catch(async e=>{console.error('Actual TEST explorer browser failed: '+e.message);if(diagnose){const d=await Promise.race([diagnose(),delay(3000).then(()=>({diagnostic_timeout:true}))]);fs.writeFileSync(out+'/browser-failure.json',JSON.stringify(d,null,2));console.log(JSON.stringify(d));}process.exitCode=1;}).finally(async()=>{if(socket)socket.close();if(browser&&browser.exitCode===null){const done=new Promise(r=>browser.once('exit',r));browser.kill();await done;}fs.rmSync(profile,{recursive:true,force:true,maxRetries:3,retryDelay:100});});
