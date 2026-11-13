'use strict';
const fs=require('fs'),cp=require('child_process'),os=require('os'),path=require('path'),assert=require('assert').strict;
const out='/tmp/robingraph-explorer-cache-20261110',origin=process.argv[2]||'https://robingraph-test.dove-nest.com';
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
 const wait=async expression=>{for(let i=0;i<700;i++){if(await evaluate(expression))return;await delay(100);}throw Error('Browser condition timeout');};
 await send('Page.enable');await send('Runtime.enable');await send('Network.enable');
 await send('Emulation.setDeviceMetricsOverride',{width:1280,height:1000,deviceScaleFactor:1,mobile:false});
 await send('Page.navigate',{url:origin+'/explore?species_scope=all&taxon=Buteo'});
 await wait('document.readyState==="complete" && !!document.querySelector("form")');
 await wait(`document.querySelectorAll('.explore-species-card').length>0`);


 const checks=[];
 const openTarget=async()=>{await evaluate(`Array.from(document.querySelectorAll('.explore-species-card')).find(c=>c.querySelector('.explore-species-sci')?.textContent==='Buteo buteo').querySelector('.explore-profile-link').click()`); await wait(`!!document.querySelector('dialog[open] .species-card')`);};
 const start=Date.now();await openTarget();const openMs=Date.now()-start;
 await wait(`!!document.querySelector('dialog[open] .species-media img')?.complete && document.querySelector('dialog[open] .species-media img').naturalWidth>0`);const photoMs=Date.now()-start;
 await wait(`document.querySelector('dialog[open] [data-observation-state]')?.getAttribute('data-observation-state')!=='pending'`);const notesMs=Date.now()-start;
 const state=await evaluate(`document.querySelector('dialog[open] [data-observation-state]').getAttribute('data-observation-state')`);
 for(const width of [1280,390,320]){
  await send('Emulation.setDeviceMetricsOverride',{width,height:1000,deviceScaleFactor:1,mobile:width<600});await delay(500);
  await evaluate(`document.querySelector('dialog[open] .species-card').showFront()`);
  let shot=await send('Page.captureScreenshot',{format:'png'});fs.writeFileSync(out+'/front-'+width+'.png',Buffer.from(shot.data,'base64'));
  await evaluate(`document.querySelector('dialog[open] .species-card').focus()`);
  await send('Input.dispatchKeyEvent',{type:'keyDown',key:'Enter',code:'Enter',windowsVirtualKeyCode:13});await send('Input.dispatchKeyEvent',{type:'keyUp',key:'Enter',code:'Enter',windowsVirtualKeyCode:13});
  await wait(`document.querySelector('dialog[open] .species-card').getAttribute('aria-label').includes('뒷면')`);await delay(500);
  const r=await evaluate(`(()=>{const d=document.querySelector('dialog[open]'),b=d.querySelector('.species-card-back'),r=d.getBoundingClientRect();return {width:innerWidth,documentWidth:document.documentElement.scrollWidth,left:r.left,right:r.right,massRows:[...b.querySelectorAll('.trait-card')].filter(n=>n.querySelector('strong')?.textContent==='체중').map(n=>n.querySelector('.trait-value')?.textContent),sourceLinks:[...b.querySelectorAll('.explore-profile-sources a')].map(a=>a.href)};})()`);
  assert.deepEqual(r.massRows,['759.1 g']);assert.equal(r.width,r.documentWidth);assert.ok(r.left>=-1&&r.right<=width+1);
  assert.ok(r.sourceLinks.some(x=>x.includes('34480856')));assert.ok(r.sourceLinks.some(x=>x.includes('5631081')));checks.push({...r,sourceLinks:undefined,sources_preserved:true});
  shot=await send('Page.captureScreenshot',{format:'png'});fs.writeFileSync(out+'/back-'+width+'.png',Buffer.from(shot.data,'base64'));
 }
 await evaluate(`document.querySelector('dialog[open] .species-popup-close').click()`);await wait(`!document.querySelector('dialog.species-popup')`);
 const beforeReload=requests.length;
 await send('Page.reload');await wait(`document.querySelectorAll('.explore-species-card').length>0`);
 const warm=Date.now();await openTarget();await wait(`!!document.querySelector('dialog[open] .species-media img')?.complete && document.querySelector('dialog[open] .species-media img').naturalWidth>0`);const reloadPhotoMs=Date.now()-warm;
 const warmRequests=requests.slice(beforeReload).filter(x=>x.url.includes('/v1/taxa/profile?'));
 assert.ok(warmRequests.length>=1);
 assert.equal(exceptions.length,0);assert.equal(requests.filter(x=>x.url.includes('/v1/chat')).length,0);
 const report={source_sha256:JSON.parse(fs.readFileSync(out+'/test-release.json')).source_sha256,origin,actual_test_browser:true,timings:{open_ms:openMs,photo_ms:photoMs,notes_settled_ms:notesMs,notes_state:state,reload_photo_ms:reloadPhotoMs,reload_profile_requests:warmRequests.length},checks,page_exceptions:exceptions.length,physical_mobile_tested:false,production_changed:false};
 fs.writeFileSync(out+'/actual-browser.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report));await send('Browser.close');
})().catch(async e=>{console.error('Actual TEST explorer browser failed: '+e.message);if(diagnose){const d=await Promise.race([diagnose(),delay(3000).then(()=>({diagnostic_timeout:true}))]);fs.writeFileSync(out+'/browser-failure.json',JSON.stringify(d,null,2));console.log(JSON.stringify(d));}process.exitCode=1;}).finally(async()=>{if(socket)socket.close();if(browser&&browser.exitCode===null){const done=new Promise(r=>browser.once('exit',r));browser.kill();await done;}fs.rmSync(profile,{recursive:true,force:true,maxRetries:3,retryDelay:100});});
