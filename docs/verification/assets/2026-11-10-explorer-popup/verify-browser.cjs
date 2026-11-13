'use strict';
const fs=require('fs'),cp=require('child_process'),os=require('os'),path=require('path'),assert=require('assert').strict;
const out='/tmp/robingraph-explorer-popup-20261110',origin=process.argv[2]||'https://robingraph-test.dove-nest.com';
assert.ok(['https://robingraph-test.dove-nest.com','http://192.168.219.97:8000'].includes(origin));
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
 diagnose=()=>evaluate(`({url:location.href,title:document.title,body:document.body?.innerText.slice(0,2000),status:document.getElementById('explore-status')?.textContent,cards:document.querySelectorAll('.explore-species-card').length,scripts:[...document.scripts].map(x=>x.src)})`);
 const wait=async expression=>{for(let i=0;i<100;i++){if(await evaluate(expression))return;await delay(100);}throw Error('Browser condition timeout');};
 await send('Page.enable');await send('Runtime.enable');await send('Network.enable');
 await send('Emulation.setDeviceMetricsOverride',{width:1280,height:1000,deviceScaleFactor:1,mobile:false});
 await send('Page.navigate',{url:origin+'/explore?species_scope=korea&taxon=Passeriformes&habitat=Forest&diet=fruit'});
 await wait('document.readyState==="complete" && !!document.querySelector("form")');
 await wait(`document.querySelectorAll('.explore-species-card').length===20`);

 const checks=[];
 const search=await evaluate('location.search');
 const name=await evaluate(`document.querySelector('.explore-species-sci').textContent`);
 for(const width of [1280,390,320]) {
  await send('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:width<=390});
  await evaluate(`document.querySelector('.explore-profile-link').focus()`);
  await send('Input.dispatchKeyEvent',{type:'keyDown',key:'Enter',code:'Enter',windowsVirtualKeyCode:13,text:'\r',unmodifiedText:'\r'});
  await send('Input.dispatchKeyEvent',{type:'keyUp',key:'Enter',code:'Enter',windowsVirtualKeyCode:13});
  await wait(`!!document.querySelector('dialog.species-popup[open] .species-card')`);
  await delay(800);
  const result=await evaluate(`(()=>{const dialog=document.querySelector('dialog.species-popup[open]'),card=dialog.querySelector('.species-card'),r=dialog.getBoundingClientRect();return {width:innerWidth,documentWidth:document.documentElement.scrollWidth,dialogLeft:r.left,dialogRight:r.right,dialogTop:r.top,dialogBottom:r.bottom,name:card.querySelector('.species-scientific-name')?.textContent,url:location.search,label:dialog.getAttribute('aria-label')};})()`);
  assert.equal(result.name,name); assert.equal(result.url,search);
  assert.equal(result.width,result.documentWidth);assert.ok(result.dialogLeft>=-1&&result.dialogRight<=width+1);
  const shot=await send('Page.captureScreenshot',{format:'png'});fs.writeFileSync(out+'/popup-'+width+'.png',Buffer.from(shot.data,'base64'));
  await evaluate(`document.querySelector('dialog[open] .species-card').focus()`);
  await send('Input.dispatchKeyEvent',{type:'keyDown',key:'Enter',code:'Enter',windowsVirtualKeyCode:13});
  await send('Input.dispatchKeyEvent',{type:'keyUp',key:'Enter',code:'Enter',windowsVirtualKeyCode:13});
  await wait(`document.querySelector('dialog[open] .species-card').getAttribute('aria-label').includes('뒷면')`);
  if(width===1280){await send('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});await send('Input.dispatchKeyEvent',{type:'keyUp',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});}
  else {await evaluate(`document.querySelector('dialog[open] .species-popup-close').click()`);}
  await wait(`!document.querySelector('dialog.species-popup')`);
  assert.equal(await evaluate(`document.activeElement.className`),'explore-profile-link');
  assert.equal(await evaluate(`document.querySelectorAll('.explore-species-card').length`),20);
  checks.push(result);
 }
 const profileRequests=requests.filter(x=>x.url.includes('/v1/taxa/profile?'));
 assert.ok(profileRequests.length>=3);assert.ok(profileRequests.every(x=>new URL(x.url).searchParams.get('species_scope')==='korea'));
 assert.equal(exceptions.length,0);assert.equal(requests.filter(x=>x.url.includes('/v1/chat')).length,0);
 const report={source_sha256:JSON.parse(fs.readFileSync(out+'/test-release.json','utf8')).source_sha256,origin,actual_test_browser:true,checks,keyboard_open:true,keyboard_flip:true,escape_close:true,close_button:true,focus_restored:true,results_preserved:true,profile_requests:profileRequests.length,page_exceptions:exceptions.length,physical_mobile_tested:false,production_changed:false};
 fs.writeFileSync(out+'/actual-browser.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report));await send('Browser.close');
})().catch(async e=>{console.error('Actual TEST explorer browser failed: '+e.message);if(diagnose){const d=await Promise.race([diagnose(),delay(3000).then(()=>({diagnostic_timeout:true}))]);fs.writeFileSync(out+'/browser-failure.json',JSON.stringify(d,null,2));console.log(JSON.stringify(d));}process.exitCode=1;}).finally(async()=>{if(socket)socket.close();if(browser&&browser.exitCode===null){const done=new Promise(r=>browser.once('exit',r));browser.kill();await done;}fs.rmSync(profile,{recursive:true,force:true,maxRetries:3,retryDelay:100});});
