'use strict';
const fs=require('fs'),cp=require('child_process'),os=require('os'),path=require('path'),assert=require('assert').strict;
const out='/tmp/robingraph-explorer-pagination-20261111',origin=process.argv[2]||'https://robingraph-test.dove-nest.com';
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


 const route='/explore?species_scope=korea&taxon=Passeriformes&habitat=Forest&diet=fruit';
 await send('Page.navigate',{url:origin+route});
 await wait(`document.querySelector('#explore-page-top') && !document.querySelector('#explore-results').hidden`);
 const api=async page=>evaluate(`fetch('/v1/taxa/explore?species_scope=korea&taxon=Passeriformes&habitat=Forest&diet=fruit&page=${page}').then(async r=>({status:r.status,body:await r.json()}))`);
 console.log('initial page ready'); const first=await api(1);assert.equal(first.status,200);const meta=first.body.pagination;
 assert.ok(meta.total_pages>1);assert.equal(meta.page_size,20);
 const pages=[first.body];for(let p=2;p<=meta.total_pages;p++){const r=await api(p);assert.equal(r.status,200);pages.push(r.body);}
 const items=pages.flatMap(p=>p.items);assert.equal(items.length,meta.total);
 const keys=items.map(i=>i.taxon.taxon_id||i.taxon.scientific_name);assert.equal(new Set(keys).size,meta.total);
 const shares=items.map(i=>Number(i.paths.map(p=>p.text).join(' ').match(/열매 (\d+(?:\.\d+)?)%/)[1]));
 assert.ok(shares.every((v,i)=>!i||v<=shares[i-1]));
 const invalid=await api(0);assert.equal(invalid.status,422);
 const clamp=await api(10000);assert.equal(clamp.body.pagination.page,meta.total_pages);assert.equal(clamp.body.query.page,meta.total_pages);
 console.log('all API pages verified'); assert.equal(await evaluate(`document.querySelectorAll('.explore-pagination').length`),2);
 assert.equal(await evaluate(`document.querySelector('#explore-page-top').previousElementSibling.disabled`),true);
 await evaluate(`document.querySelector('#explore-page-top').nextElementSibling.focus()`);
 await send('Input.dispatchKeyEvent',{type:'keyDown',key:'Enter',code:'Enter',text:'\r',windowsVirtualKeyCode:13});await send('Input.dispatchKeyEvent',{type:'keyUp',key:'Enter',code:'Enter',windowsVirtualKeyCode:13});
 await wait(`document.querySelector('#explore-page-top')?.value==='2' && document.activeElement?.id==='explore-page-top'`);
 assert.equal(await evaluate(`new URLSearchParams(location.search).get('page')`),'2');
 console.log('keyboard page two ready'); await send('Page.reload');await wait(`document.querySelector('#explore-page-top')?.value==='2'`);
 await evaluate(`(()=>{const s=document.querySelector('#explore-page-bottom');s.value='${meta.total_pages}';s.dispatchEvent(new Event('change',{bubbles:true}));})()`);
 await wait(`document.querySelector('#explore-page-top')?.value==='${meta.total_pages}' && !document.querySelector('#explore-results').hidden`);
 assert.equal(await evaluate(`document.querySelectorAll('.explore-species-card').length`),meta.total-(meta.total_pages-1)*20);
 assert.equal(await evaluate(`document.querySelector('#explore-page-top').nextElementSibling.disabled`),true);
 console.log('last page ready'); const layout=[];
 await send('Emulation.setEmulatedMedia',{features:[{name:'prefers-color-scheme',value:'dark'}]});
 for(const width of [1280,390,320]){
  await send('Emulation.setDeviceMetricsOverride',{width,height:1000,deviceScaleFactor:1,mobile:width<600});
  const r=await evaluate(`({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,scheme:getComputedStyle(document.documentElement).colorScheme,range:document.querySelector('.explore-page-range').textContent})`);
  assert.equal(r.width,r.scrollWidth);assert.ok(r.scheme.includes('light'));layout.push(r);
  const shot=await send('Page.captureScreenshot',{format:'png'});fs.writeFileSync(out+'/pagination-'+width+'.png',Buffer.from(shot.data,'base64'));
 }

 await evaluate(`(()=>{const e=document.querySelector('#explore-diet-fruit');e.checked=false;e.dispatchEvent(new Event('change',{bubbles:true}));})()`);
 assert.equal(await evaluate(`document.querySelector('#explore-results').hidden`),true);
 await evaluate(`document.querySelector('#explore-form').requestSubmit()`);
 await wait(`!document.querySelector('#explore-results').hidden && !!document.querySelector('#explore-page-top') && document.querySelector('#explore-page-top').value==='1'`);
 assert.equal(await evaluate(`new URLSearchParams(location.search).has('page')`),false);
 const natural=await evaluate(`(async()=>{const pages=await Promise.all([1,2].map(p=>fetch('/v1/taxa/explore?species_scope=korea&taxon=Passeriformes&habitat=Forest&page='+p).then(r=>r.json())));return pages.map(p=>({pagination:p.pagination,names:p.items.map(i=>i.taxon.scientific_name)}));})()`);
 assert.equal(natural[0].pagination.page,1);assert.equal(natural[1].pagination.page,2);assert.equal(natural[0].names.length,20);assert.equal(natural[1].names.length,20);
 assert.equal(new Set(natural.flatMap(p=>p.names)).size,40);
 const report={source_sha256:JSON.parse(fs.readFileSync(out+'/test-release.json')).source_sha256,origin,actual_test_browser:true,pagination:meta,all_pages_unique:true,global_diet_order:true,keyboard_next:true,reload_restores_page:true,dropdown_last_page:true,clamps_large_page:true,invalid_page_422:true,filter_change_resets_page:true,natural_pages_unique:true,layout,page_exceptions:exceptions.length,physical_mobile_tested:false,production_changed:false};
 assert.equal(exceptions.length,0);fs.writeFileSync(out+'/actual-browser.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report));await send('Browser.close');
})().catch(async e=>{console.error('Actual TEST explorer browser failed: '+e.message);if(diagnose){const d=await Promise.race([diagnose(),delay(3000).then(()=>({diagnostic_timeout:true}))]);fs.writeFileSync(out+'/browser-failure.json',JSON.stringify(d,null,2));console.log(JSON.stringify(d));}process.exitCode=1;}).finally(async()=>{if(socket)socket.close();if(browser&&browser.exitCode===null){const done=new Promise(r=>browser.once('exit',r));browser.kill();await done;}fs.rmSync(profile,{recursive:true,force:true,maxRetries:3,retryDelay:100});});
