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
 await send('Page.navigate',{url:origin+'/explore?species_scope=all&taxon=Asio'});
 await wait('document.readyState==="complete" && !!document.querySelector("form")');
 await wait(`document.querySelectorAll('.explore-species-card').length>0`);



 const started=Date.now();const before=requests.length;
 await evaluate(`Array.from(document.querySelectorAll('.explore-species-card')).find(c=>c.querySelector('.explore-species-sci')?.textContent==='Asio otus').querySelector('.explore-profile-link').click()`);
 await wait(`!!document.querySelector('dialog[open] .species-card')`);const opened=Date.now()-started;
 await wait(`!!document.querySelector('dialog[open] .species-media img')?.complete && document.querySelector('dialog[open] .species-media img').naturalWidth>0`);
 const readyMs=Date.now()-started;
 assert.equal(await evaluate(`document.querySelector('dialog[open] [data-observation-state]').getAttribute('data-observation-state')`),'ready');
 const profileRequests=requests.slice(before).filter(x=>x.url.includes('/v1/taxa/profile?'));
 assert.equal(profileRequests.length,1);assert.equal(new URL(profileRequests[0].url).searchParams.get('defer_enrichment'),'true');assert.equal(exceptions.length,0);
 const shot=await send('Page.captureScreenshot',{format:'png'});fs.writeFileSync(out+'/cached-asio.png',Buffer.from(shot.data,'base64'));
 const report={species:'Asio otus',prepopulated_public_metadata:true,new_page:true,open_ms:opened,photo_and_notes_ready_ms:readyMs,profile_requests:profileRequests.length,notes_state:'ready',page_exceptions:0};
 fs.writeFileSync(out+'/cached-browser.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report));await send('Browser.close');
})().catch(async e=>{console.error('Actual TEST explorer browser failed: '+e.message);if(diagnose){const d=await Promise.race([diagnose(),delay(3000).then(()=>({diagnostic_timeout:true}))]);fs.writeFileSync(out+'/browser-failure.json',JSON.stringify(d,null,2));console.log(JSON.stringify(d));}process.exitCode=1;}).finally(async()=>{if(socket)socket.close();if(browser&&browser.exitCode===null){const done=new Promise(r=>browser.once('exit',r));browser.kill();await done;}fs.rmSync(profile,{recursive:true,force:true,maxRetries:3,retryDelay:100});});
