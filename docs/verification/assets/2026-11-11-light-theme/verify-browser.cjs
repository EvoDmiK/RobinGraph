'use strict';
const fs=require('fs'),cp=require('child_process'),os=require('os'),path=require('path'),assert=require('assert').strict;
const out='/tmp/robingraph-light-theme-20261111',origin=process.argv[2]||'https://robingraph-test.dove-nest.com';
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

 const checks=[];
 const routes=[['chat','/chat'],['explore','/explore?species_scope=all&taxon=Asio'],['birds','/birds?name=Asio%20otus'],['audio-review','/audio-review']];
 for(const width of [1280,390]) {
  await send('Emulation.setDeviceMetricsOverride',{width,height:1000,deviceScaleFactor:1,mobile:width<600});
  for(const [name,route] of routes) {
   const palettes=[];
   for(const preference of ['light','dark']) {
    await send('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:preference}]});
    await send('Page.navigate',{url:origin+route});await wait(`document.readyState==='complete' && !!document.querySelector('.page')`);
    const r=await evaluate(`(()=>{const root=getComputedStyle(document.documentElement),body=getComputedStyle(document.body),control=document.querySelector('input,select,button');return {scheme:root.colorScheme,background:body.backgroundColor,text:body.color,darkRequested:matchMedia('(prefers-color-scheme: dark)').matches,controlScheme:control?getComputedStyle(control).colorScheme:null,width:innerWidth,documentWidth:document.documentElement.scrollWidth};})()`);
    assert.equal(r.background,'rgb(248, 243, 231)');assert.equal(r.text,'rgb(42, 39, 31)');assert.ok(r.scheme.includes('light')&&!r.scheme.includes('dark'));assert.equal(r.darkRequested,preference==='dark');assert.equal(r.width,r.documentWidth);
    if(r.controlScheme)assert.ok(r.controlScheme.includes('light')&&!r.controlScheme.includes('dark'));
    palettes.push({background:r.background,text:r.text,scheme:r.scheme});checks.push({page:name,preference,...r});
    if(preference==='dark'){const shot=await send('Page.captureScreenshot',{format:'png'});fs.writeFileSync(out+'/'+name+'-dark-os-'+width+'.png',Buffer.from(shot.data,'base64'));}
   }
   assert.deepEqual(palettes[0],palettes[1]);
  }
 }
 assert.equal(exceptions.length,0);
 const report={source_sha256:JSON.parse(fs.readFileSync(out+'/test-release.json')).source_sha256,origin,actual_test_browser:true,checks,light_dark_palette_identical:true,page_exceptions:0,physical_mobile_tested:false,production_changed:false};
 fs.writeFileSync(out+'/actual-browser.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report));await send('Browser.close');
})().catch(async e=>{console.error('Actual TEST explorer browser failed: '+e.message);if(diagnose){const d=await Promise.race([diagnose(),delay(3000).then(()=>({diagnostic_timeout:true}))]);fs.writeFileSync(out+'/browser-failure.json',JSON.stringify(d,null,2));console.log(JSON.stringify(d));}process.exitCode=1;}).finally(async()=>{if(socket)socket.close();if(browser&&browser.exitCode===null){const done=new Promise(r=>browser.once('exit',r));browser.kill();await done;}fs.rmSync(profile,{recursive:true,force:true,maxRetries:3,retryDelay:100});});
